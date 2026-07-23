"""
rag-api-cloud - API FastAPI que expone el sistema RAG (rag-second-brain)
sobre Amazon Bedrock (Titan Embeddings + Claude/Titan para generación).

Endpoints:
  GET  /health   -> liveness check (usado por el ALB target group)
  POST /query    -> pregunta al RAG, devuelve respuesta + metadata de observabilidad
  GET  /metrics  -> contador simple en memoria (demo; en real usarías CloudWatch)
"""

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import boto3
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.rag_pipeline import RAGPipeline

settings = get_settings()

# Estado compartido simple para métricas de demo. En producción esto
# se reemplaza por CloudWatch Embedded Metric Format o un backend real.
METRICS = {"total_queries": 0, "total_tokens": 0, "avg_latency_ms": 0.0}


def sync_chroma_from_s3() -> None:
    """Descarga el indice de Chroma desde S3 antes de arrancar.

    El indice NO viaja en la imagen Docker ni en el repo de git (el
    .gitignore excluye data/ a proposito: contiene embeddings de notas
    privadas). En su lugar, se sube una vez a un bucket S3 privado
    (aws s3 sync data/chroma s3://<bucket>/chroma-data/) y el
    contenedor lo descarga aca, al arrancar, usando el permiso IAM del
    task role (sin credenciales estaticas).

    Si RAG_CHROMA_S3_BUCKET no esta seteado (caso local con
    docker-compose, que monta el volumen directo), esta funcion no
    hace nada.
    """
    if not settings.chroma_s3_bucket:
        print("RAG_CHROMA_S3_BUCKET no configurado, usando indice local existente")
        return

    print(f"Sincronizando indice de Chroma desde s3://{settings.chroma_s3_bucket}/{settings.chroma_s3_prefix}...")
    s3 = boto3.client("s3")
    dest_root = Path(settings.chroma_persist_dir)
    dest_root.mkdir(parents=True, exist_ok=True)

    paginator = s3.get_paginator("list_objects_v2")
    downloaded = 0
    for page in paginator.paginate(Bucket=settings.chroma_s3_bucket, Prefix=settings.chroma_s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            relative_path = key[len(settings.chroma_s3_prefix):]
            if not relative_path:
                continue
            local_path = dest_root / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(settings.chroma_s3_bucket, key, str(local_path))
            downloaded += 1

    print(f"Listo: {downloaded} archivos descargados a {dest_root}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_chroma_from_s3()
    # Carga el pipeline (conexión a ChromaDB + cliente Bedrock) una sola vez
    # al arrancar el contenedor, no en cada request.
    app.state.rag = RAGPipeline(settings)
    yield


app = FastAPI(title="rag-api-cloud", version="0.1.0", lifespan=lifespan)


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Auth minima por API key para un proyecto de portafolio.

    Nota deliberada: para producción real esto se reemplazaria por
    Cognito/IAM auth en el ALB o un API Gateway con autorizador. Una
    API key fija es suficiente para demostrar el patron sin anadir
    complejidad de IdP a un proyecto de portafolio.
    """
    if not settings.api_key:
        return  # auth deshabilitada explicitamente via env var (solo demo local)
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API key invalida o ausente")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class QueryResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[str]
    retrieval_score: float
    tokens_used: int
    latency_ms: float


@app.get("/health")
def health() -> dict:
    """Liveness check. El ALB target group hace polling aca cada N segundos."""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def query(payload: QueryRequest) -> QueryResponse:
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    result = await app.state.rag.answer(payload.question, top_k=payload.top_k)

    latency_ms = (time.perf_counter() - start) * 1000
    METRICS["total_queries"] += 1
    METRICS["total_tokens"] += result.tokens_used
    METRICS["avg_latency_ms"] = (
        METRICS["avg_latency_ms"] * (METRICS["total_queries"] - 1) + latency_ms
    ) / METRICS["total_queries"]

    return QueryResponse(
        request_id=request_id,
        answer=result.answer,
        sources=result.sources,
        retrieval_score=result.retrieval_score,
        tokens_used=result.tokens_used,
        latency_ms=round(latency_ms, 1),
    )


@app.get("/metrics")
def metrics() -> dict:
    """Observabilidad basica de LLMOps: volumen, costo (via tokens) y latencia."""
    return METRICS
