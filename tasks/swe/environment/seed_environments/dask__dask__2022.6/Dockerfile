FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/dask/dask.git /testbed

# Pin version 2022.6.x of the repo.
RUN git fetch --tags && git checkout $(git rev-list -n 1 --before="2022-07-01" main 2>/dev/null || echo HEAD)

RUN pip install --upgrade pip setuptools wheel

RUN pip install \
        "numpy>=1.18,<1.24" \
        "pandas>=1.0" \
        "toolz>=0.8.2" \
        "partd>=1.2.0" \
        "cloudpickle>=1.1.1" \
        "fsspec>=0.6.0" \
        "pyyaml>=5.3.1" \
        pytest \
        pytest-xdist

RUN pip install -e '.[complete]'
