from functools import lru_cache
 
from pydantic_settings import BaseSettings
 
 
class Settings(BaseSettings):
    # Nada de credenciales estaticas aqui: el task role de ECS le da
    # al contenedor permisos IAM para llamar a Bedrock sin claves.
    bedrock_region: str = "us-east-1"
    # anthropic.claude-3-5-haiku-20241022-v1:0 fue retirado de Bedrock
    # (ResourceNotFoundException: "reached end of life"). Sucesor: Haiku
    # 4.5, invocado via cross-region inference profile (prefijo "us.").
    bedrock_llm_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
 
    chroma_persist_dir: str = "/data/chroma"
 
    # Vacio = auth deshabilitada (solo para correr local en dev).
    api_key: str = ""
 
    class Config:
        env_prefix = "RAG_"
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()
 