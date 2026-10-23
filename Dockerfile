FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY web ./web
COPY data/uk/corpus.jsonl.gz data/uk/changes.jsonl.gz data/uk/timeline_steps.json.gz ./data/uk/
RUN pip install --no-cache-dir ".[api]" \
    && useradd --system --uid 10001 --no-create-home taadeel
# Run as an unprivileged user; the app only reads files and makes no outbound calls at run time.
USER taadeel
ENV PORT=8000 TAADEEL_ROOT=/app PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=4)"
CMD ["sh", "-c", "uvicorn taadeel.api:app --host 0.0.0.0 --port ${PORT}"]
