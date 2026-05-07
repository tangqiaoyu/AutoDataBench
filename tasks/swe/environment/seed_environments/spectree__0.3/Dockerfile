FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/0b01001001/spectree.git /testbed

# Check out the exact base_commit — the v0.3 tag doesn't exist in this repo,
# so the old fallback landed on HEAD whose setup.py requires Python >=3.10.
RUN git checkout a091fab020ac26548250c907bae0855273a98778

RUN pip install --upgrade pip setuptools wheel

# Base runtime deps + test harness; mirrors SWE-rebench install_config.pip_packages.
RUN pip install pytest

# Editable install with the extras the project ships.
RUN pip install -e '.[flask,falcon,starlette]'
