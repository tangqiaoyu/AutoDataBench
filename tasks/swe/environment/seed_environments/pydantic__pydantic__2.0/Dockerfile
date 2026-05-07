FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/pydantic/pydantic.git /testbed
RUN git checkout ef3cc495a9c86553b62a95a6052fd9b6ebc045e9

RUN pip install --upgrade pip setuptools wheel

# Hard-pin pydantic-core to the version pydantic/_internal was coded against.
# This commit expects core_schema.JsonReturnTypes — exposed in 0.8.2, removed
# in later pydantic-core releases. pyproject.toml only says >=0.8.2, so we
# must pin explicitly here. annotated-types is also required at runtime
# (pyproject declares it but --no-deps below skips it; testing.txt omits it).
RUN pip install "pydantic-core==0.8.2" "annotated-types>=0.4.0"

# Test runtime deps from the repo's own testing.txt (dirty-equals, pytest-mock, etc.)
RUN pip install -r requirements/testing.txt

# --no-deps so pip doesn't upgrade pydantic-core through the >=0.8.2 constraint.
RUN pip install --no-deps -e .
