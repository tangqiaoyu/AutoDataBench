FROM python:3.9-slim

# sepal_ui pulls in geospatial stack (rasterio / fiona via pip wheels) and ipyleaflet —
# wheels usually suffice on slim, but keep build-essential for fallbacks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/12rambau/sepal_ui.git /testbed

# Pin version 2.8 of the repo.
RUN git fetch --tags && git checkout v2.8.0 || git checkout $(git rev-list -n 1 --before="2022-05-01" main 2>/dev/null || echo HEAD)

RUN pip install --upgrade pip setuptools wheel

RUN pip install pytest coverage python-box

RUN pip install -e '.[dev]'
