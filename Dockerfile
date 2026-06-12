FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY onepager ./onepager
COPY examples ./examples
RUN pip install --no-cache-dir ".[web]"

EXPOSE 8000
CMD ["sh", "-c", "uvicorn onepager.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
