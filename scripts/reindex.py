"""
scripts/reindex.py

Reconstruye la coleccion de ChromaDB usando Titan Embeddings (Bedrock)
en vez de nomic-embed-text (Ollama). Necesario porque rag-api-cloud
consulta el indice con Titan en tiempo de query (ver app/rag_pipeline.py)
y el espacio vectorial de un modelo de embeddings no es compatible con
el de otro: mezclar ambos en la misma coleccion da resultados sin
sentido, no un error visible.

La lectura del vault y el chunking son IDENTICOS a los de
rag-second-brain/Index_vault.py (load_vault_documents, MarkdownTextSplitter
con chunk_size=800 / chunk_overlap=120) para que el corpus indexado sea
el mismo; solo cambia que embeb con.

Uso:
    python scripts/reindex.py /ruta/al/vault
"""

import json
import sys
import time
from pathlib import Path

import boto3
import chromadb
import yaml
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter

import os

IGNORE_DIRS = {".obsidian", ".git", ".trash", "_attachments", ".vscode"}
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
BEDROCK_REGION = "us-east-1"
COLLECTION_NAME = "second_brain"
# Relativo por defecto: funciona corriendo local (Windows/Mac/Linux) desde
# la carpeta del proyecto. Dentro del contenedor Docker, docker-compose.yml
# ya define RAG_CHROMA_PERSIST_DIR=/data/chroma, que pisa este default.
CHROMA_PERSIST_DIR = os.environ.get("RAG_CHROMA_PERSIST_DIR", "./data/chroma")
BATCH_SIZE = 50


def extract_frontmatter_tags(text: str) -> list[str]:
    """Extrae tags del frontmatter YAML (--- ... --- al inicio de la nota).

    NOTA: reconstruida a partir de la descripcion del comportamiento de
    rag-second-brain, no del codigo original de esa funcion. Si tu
    Index_vault.py tiene una implementacion distinta (ej. tags anidados,
    formato #tag inline ademas de frontmatter), reemplaza esta funcion
    por la tuya antes de correr el reindex -- el resto del script no
    depende de los detalles internos, solo de que devuelva list[str].
    """
    if not text.startswith("---"):
        return []
    try:
        end = text.index("---", 3)
    except ValueError:
        return []
    try:
        data = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return []
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    return list(tags)


def load_vault_documents(vault_path: Path) -> list[Document]:
    """Identico a rag-second-brain/Index_vault.py:51-76."""
    docs = []
    for md_file in vault_path.rglob("*.md"):
        if any(part in IGNORE_DIRS for part in md_file.parts):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [!] No se pudo leer {md_file}: {e}")
            continue

        rel_path = md_file.relative_to(vault_path).as_posix()
        tags = extract_frontmatter_tags(text)

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": rel_path,
                    "folder": rel_path.split("/")[0],
                    "tags": ", ".join(tags),
                },
            )
        )
    return docs


def embed_titan(bedrock_client, text: str, max_retries: int = 5) -> list[float]:
    """Un chunk por request: la API de Titan Embeddings no acepta batch
    en un solo invoke_model. Con retry exponencial ante throttling, que
    es esperable si indexas varios miles de chunks seguidos."""
    body = json.dumps({"inputText": text})
    for attempt in range(max_retries):
        try:
            response = bedrock_client.invoke_model(
                modelId=EMBEDDING_MODEL_ID,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            return payload["embedding"]
        except bedrock_client.exceptions.ThrottlingException:
            wait_seconds = 2 ** attempt
            print(f"    [!] Throttled por Bedrock, reintentando en {wait_seconds}s...")
            time.sleep(wait_seconds)
    raise RuntimeError("Bedrock siguio bloqueando el request tras varios reintentos")


def main(vault_path_str: str) -> None:
    vault_path = Path(vault_path_str)
    if not vault_path.is_dir():
        print(f"[!] {vault_path} no es un directorio valido")
        sys.exit(1)

    print(f"Leyendo vault en {vault_path}...")
    documents = load_vault_documents(vault_path)
    print(f"  {len(documents)} notas encontradas")

    splitter = MarkdownTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(documents)
    print(f"  {len(chunks)} chunks generados")

    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # Espacio vectorial distinto al de nomic-embed-text: se recrea la
    # coleccion desde cero. No tiene sentido "agregar" a la vieja.
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print(f"  Coleccion '{COLLECTION_NAME}' anterior eliminada")
    except Exception:
        pass
    collection = chroma_client.create_collection(COLLECTION_NAME)

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        ids = [f"{c.metadata['source']}::{i + j}" for j, c in enumerate(batch)]
        embeddings = [embed_titan(bedrock, c.page_content) for c in batch]
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=[c.page_content for c in batch],
            metadatas=[c.metadata for c in batch],
        )
        print(f"  Indexados {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks")

    print(f"Listo. '{COLLECTION_NAME}' reconstruida con Titan Embeddings en {CHROMA_PERSIST_DIR}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/reindex.py /ruta/al/vault")
        sys.exit(1)
    main(sys.argv[1])
