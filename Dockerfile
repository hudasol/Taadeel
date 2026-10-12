FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY web ./web
COPY data/uk/corpus.jsonl.gz data/uk/changes.jsonl.gz ./data/uk/
RUN pip install --no-cache-dir ".[api]"
ENV PORT=8000 TAADEEL_ROOT=/app
CMD ["sh", "-c", "uvicorn taadeel.api:app --host 0.0.0.0 --port ${PORT}"]
