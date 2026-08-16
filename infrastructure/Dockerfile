FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev,linkedin,web,google]"

COPY src/ ./src/
COPY infrastructure/ ./infrastructure/

RUN useradd -m -u 1000 jobhunt && \
    mkdir -p /app/data /app/credentials && \
    chown -R jobhunt:jobhunt /app

USER jobhunt

ENV PATH="/home/jobhunt/.local/bin:${PATH}"

ENTRYPOINT ["python", "-m", "jobhunt.cli.main"]
CMD ["--help"]