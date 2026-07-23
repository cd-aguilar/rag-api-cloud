"""
Reemplaza aqui la logica de retrieval/generacion que ya tienes en
rag-second-brain. Este archivo es el punto de integracion: mismo
prompt anti-alucinacion, misma coleccion de Chroma, pero embeddings
y LLM ahora vienen de Bedrock en lugar de Ollama local.
"""

import asyncio
import json
from dataclasses import dataclass

import boto3
import chromadb

# Mismo prompt anti-alucinacion que en rag-second-brain: respuesta SOLO
# desde el contexto recuperado, y admitir explicitamente cuando no hay
# evidencia suficiente en vez de inventar.
SYSTEM_PROMPT = (
    "Sos un asistente que responde preguntas usando UNICAMENTE el contexto "
    "entregado a continuacion, extraido de la base de conocimiento del "
    "usuario. Reglas estrictas:\n"
    "1. Si la respuesta no esta en el contexto, responde exactamente: "
    "'No tengo informacion suficiente en la base de conocimiento para "
    "responder esto.'\n"
    "2. No inventes datos, fechas ni fuentes que no aparezcan en el "
    "contexto.\n"
    "3. Cita el nombre de archivo de cada fuente que uses en tu respuesta."
)


@dataclass
class RAGResult:
    answer: str
    sources: list[str]
    retrieval_score: float
    tokens_used: int


class RAGPipeline:
    def __init__(self, settings):
        self.settings = settings
        self.bedrock = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        self.chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.collection = self.chroma_client.get_or_create_collection("second_brain")

    def _embed(self, text: str) -> list[float]:
        # Titan Embeddings via Bedrock. Debe ser el MISMO modelo usado
        # para indexar el vault, o el espacio vectorial no coincide.
        body = json.dumps({"inputText": text})
        response = self.bedrock.invoke_model(
            modelId=self.settings.bedrock_embedding_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        return payload["embedding"]

    def _retrieve(self, question: str, top_k: int) -> tuple[list[str], list[str], float]:
        query_embedding = self._embed(question)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        chunks = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        sources = sorted({m.get("source", "desconocido") for m in metadatas})
        # Chroma devuelve distancia (menor = mas parecido); lo convertimos
        # a un score 0-1 donde 1 es maxima relevancia, para exponerlo en
        # /query como metrica de calidad de retrieval.
        avg_distance = sum(distances) / len(distances) if distances else 1.0
        retrieval_score = max(0.0, 1.0 - avg_distance)
        return chunks, sources, retrieval_score

    def _build_prompt(self, question: str, chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(chunks)
        return f"Contexto:\n{context}\n\nPregunta: {question}"

    def _generate(self, question: str, chunks: list[str]) -> tuple[str, int]:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": self._build_prompt(question, chunks)}
            ],
        })
        response = self.bedrock.invoke_model(
            modelId=self.settings.bedrock_llm_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        answer = payload["content"][0]["text"]
        tokens_used = payload["usage"]["input_tokens"] + payload["usage"]["output_tokens"]
        return answer, tokens_used

    async def answer(self, question: str, top_k: int = 4) -> RAGResult:
        # _retrieve y _generate son metodos sincronos: boto3 y el cliente
        # de ChromaDB no soportan async/await. Si los llamamos directo
        # desde una funcion async, bloquean el event loop de uvicorn y
        # una sola request congela a todas las demas mientras espera a
        # Bedrock. asyncio.to_thread los corre en un thread pool aparte,
        # liberando el event loop para atender otras requests mientras
        # esta espera la red.
        chunks, sources, retrieval_score = await asyncio.to_thread(
            self._retrieve, question, top_k
        )

        if not chunks:
            return RAGResult(
                answer="No tengo informacion suficiente en la base de conocimiento para responder esto.",
                sources=[],
                retrieval_score=0.0,
                tokens_used=0,
            )

        answer_text, tokens_used = await asyncio.to_thread(
            self._generate, question, chunks
        )

        return RAGResult(
            answer=answer_text,
            sources=sources,
            retrieval_score=round(retrieval_score, 3),
            tokens_used=tokens_used,
        )
