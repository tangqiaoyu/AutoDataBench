FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    tmux curl wget git vim \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# PDF reading support (agents may also use the openai/requests SDK if they choose)
RUN pip3 install --break-system-packages openai requests pymupdf

WORKDIR /home/agent
RUN mkdir -p /home/agent/resources /home/agent/submission

# Copy all resources into the container
COPY llm_api_doc.md      /home/agent/resources/llm_api_doc.md
COPY web_api_doc.md      /home/agent/resources/web_api_doc.md
COPY seed_data.jsonl     /home/agent/resources/seed_data.jsonl

# The four env vars below are placeholders. Override them at run time, e.g.:
#   docker run -e LLM_API_BASE=https://your-llm-gateway/v1 \
#              -e LLM_API_KEY=sk-... \
#              -e WEB_API_BASE=https://your-web-api \
#              -e WEB_API_KEY=... ...
ENV LLM_API_BASE=http://llm-gateway.local:8080/v1
ENV LLM_API_KEY=replace-with-your-llm-api-key
ENV WEB_API_BASE=http://web-api.local:8081
ENV WEB_API_KEY=replace-with-your-web-api-key
ENV PYTHONPATH=/home/agent/resources
ENV PYTHONUNBUFFERED=1
