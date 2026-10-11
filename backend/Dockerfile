FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-liberation fonts-lato fonts-freefont-ttf fonts-crosextra-carlito fonts-crosextra-caladea && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
COPY fonts/ /usr/share/fonts/truetype/reclipd/
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
RUN useradd -m studio && mkdir -p /data && chown studio /data
# Model cache is persistent and the worker runs without root privileges.
ENV HF_HOME=/data/model-cache
USER studio
EXPOSE 8000
