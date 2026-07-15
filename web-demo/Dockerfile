FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -e ".[dev]" httpx

ENV PACKING_API_PORT=8000
ENV WEB_DEMO_PORT=8080
ENV PACKING_API_HOST=127.0.0.1

EXPOSE 8080

CMD ["bash", "web-demo/start.sh"]
