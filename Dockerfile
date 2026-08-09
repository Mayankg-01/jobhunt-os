FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY jobhunt ./jobhunt
COPY samples ./samples

RUN pip install --no-cache-dir .

ENV JOBHUNT_DATA=/data
VOLUME ["/data"]

EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8020/health',timeout=3).status==200 else 1)"
CMD ["uvicorn", "jobhunt.api:app", "--host", "0.0.0.0", "--port", "8020"]