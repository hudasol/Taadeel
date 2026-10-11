FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY web ./web
RUN pip install --no-cache-dir ".[api]"
ENV PORT=8000
CMD ["sh", "-c", "uvicorn taadeel.api:app --host 0.0.0.0 --port ${PORT}"]
