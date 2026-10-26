FROM python:3.12-slim

# PyMuPDF wants some runtime libs; keep the image lean otherwise.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY templates/ templates/
COPY static/ static/
COPY scripts/ scripts/
COPY dataset/ dataset/
COPY eval/ eval/
COPY PLANS.md PLANS_V1-V5.md UPDATES.md README.md ./

# Run unprivileged; /srv/data holds the SQLite DB, generated files and secret key.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /srv/data && chown -R appuser:appuser /srv/app
USER appuser
ENV APP_DATA_DIR=/srv/data

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz', timeout=3)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
