FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed
RUN git clone https://github.com/getmoto/moto.git /testbed
RUN git checkout 6b70cd1b6b1cf493b66b6fcaaea9d1041331e836

RUN pip install --upgrade pip setuptools wheel

# Use the repo's own test requirements (sure, freezegun, pytest-xdist, ...).
RUN pip install -r requirements-tests.txt

# Editable install with the [all] extra pulls in runtime deps like pytz, boto3, etc.
RUN pip install -e '.[all]'
