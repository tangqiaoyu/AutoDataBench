FROM python:3.8-slim

# pygit2 needs libgit2 headers; building some wheels needs build-essential.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libgit2-dev \
        pkg-config \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/iterative/dvc.git /testbed
RUN git checkout a7d665157cd838a9406e30c249065111d93a9e4a

RUN pip install --upgrade pip setuptools wheel

# Hand-picked test-runtime deps (equivalent to setup.py's tests_require minus
# the bad 'moto==1.3.16.dev122' pin which is not on PyPI; we use moto<5 which
# still has mock_s3 symbol).
# Deps discovered iteratively from tests/conftest.py + tests/remotes/*.py imports:
#   - moto (s3 remote mocks), pre-v5 to keep mock_s3
#   - wsgidav (webdav remote tests)
#   - RangeHTTPServer (webdav/HTTP range tests)
# Everything else from tests_require that doesn't have a pypi problem.
RUN pip install \
        "pytest>=6.0.1,<8" \
        pytest-cov \
        pytest-timeout \
        pytest-xdist \
        pytest-mock \
        pytest-lazy-fixture \
        flaky \
        mock \
        "moto<5" \
        wsgidav \
        RangeHTTPServer

# Editable install with [all] remotes but not [tests] (its bad pin would break).
RUN pip install -e '.[all]'
