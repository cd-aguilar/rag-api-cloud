# --- Stage 1: build de dependencias ---
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: imagen final, liviana ---
FROM python:3.12-slim

# Usuario no-root: buena practica de seguridad, tambien la revisan
# en entrevistas y en reviews de Terraform/ECS.
RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ ./app/

# Directorio donde vive el indice de Chroma (montado via EFS en produccion,
# o incluido en la imagen para la demo si el vault es pequeno).
RUN mkdir -p /data/chroma && chown -R appuser:appuser /data /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
