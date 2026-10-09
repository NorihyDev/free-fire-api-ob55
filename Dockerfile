FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml LICENSE README.md ./
COPY freefire_api ./freefire_api
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 api
USER api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "freefire_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
