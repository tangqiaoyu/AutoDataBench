# Docker Environment Guide

Docker is available via Docker-in-Docker (DinD). Use it to build and run containers for reproducible environments, dependency isolation, and running tests.

## Setup

Point the Docker CLI at the DinD gateway:

```bash
export DOCKER_HOST="tcp://$(ip route | grep default | awk '{print $3}'):2375"
docker info       # verify connectivity
```

## Basic Usage

```bash
# Run a one-off command
docker run --rm python:3.11 python3 --version

# Start a long-lived container and exec into it
docker run -d --name worker python:3.11 sleep infinity
docker exec worker pip install pytest
docker exec worker python -c "print('hello')"

# Build an image from a Dockerfile
docker build -t my-image /path/to/build-dir
docker run --rm my-image
```

## Images

Docker Hub (`docker.io`) is reachable. Use standard image names:

```bash
docker pull python:3.11-slim
docker pull alpine:latest
docker pull ubuntu:22.04
```

### Image variants

- `python:3.11-slim` — smaller, no compiler / minimal system libs. Good for pure-Python.
- `python:3.11` — full Debian base with build tools. Needed when installing packages that compile from source (e.g. psycopg2, some numpy/scipy builds).

### Rate limit

Docker Hub applies a per-IP anonymous pull rate limit. If you see:

```
Error: toomanyrequests: You have reached your unauthenticated pull rate limit.
```

Options:

1. Wait a few minutes and retry (the limit is rolling).
2. Reuse already-pulled images — pulled images stay cached on the DinD daemon for this session.

### `docker build` deprecation warning

`docker build` prints:

```
DEPRECATED: The legacy builder is deprecated ... Install the buildx component ...
```

This is cosmetic. Builds work correctly.

## Getting Files In and Out of Containers

**Bind mounts do NOT work** — `-v /host/path:/container/path` silently fails (see [Gotchas](#gotchas)). Use `docker cp` or named volumes.

### `docker cp` — recommended for host↔container transfer

The target directory must exist. `docker cp` into a non-existent directory fails with:

```
Error response from daemon: Could not find the file /data in container ...
```

Pattern:

```bash
# Start a long-lived container
docker run -d --name worker python:3.11 sleep infinity

# 1. Create target dir FIRST
docker exec worker mkdir -p /data

# 2. Copy file in
docker cp /home/agent/data/input.csv worker:/data/input.csv

# Or copy an entire directory (note trailing /. on source)
docker cp /home/agent/data/. worker:/data/

# 3. Do work
docker exec worker python -c "import pandas; print(pandas.read_csv('/data/input.csv').sum())"

# 4. Copy results out (local target dir must exist)
mkdir -p /home/agent/output
docker cp worker:/data/result.txt /home/agent/output/

# Cleanup
docker rm -f worker
```

### `docker volume` — for container↔container sharing

```bash
docker volume create shared
docker run --rm -v shared:/data alpine sh -c 'echo hello > /data/f'
docker run --rm -v shared:/data alpine cat /data/f
docker volume rm shared
```

## Multi-Container Networking

### Custom bridge network (recommended)

On a user-defined network, each container is reachable by its `--name` as a hostname:

```bash
docker network create my-net

docker run -d --name srv --network my-net python:3.11 python -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
    def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b'ok')
HTTPServer(('0.0.0.0', 8080), H).serve_forever()
"

docker run --rm --network my-net alpine wget -qO- http://srv:8080/
```

### By container IP (default bridge)

```bash
docker run -d --name srv python:3.11 ...
SRV_IP=$(docker inspect -f '{{.NetworkSettings.IPAddress}}' srv)
docker run --rm alpine wget -qO- http://${SRV_IP}:8080/
```

### Port-publish + DinD gateway

Use the gateway IP, NOT `localhost` — `localhost` inside a container means the container itself:

```bash
GATEWAY=$(ip route | grep default | awk '{print $3}')
docker run -d --name srv -p 18080:8080 python:3.11 ...

curl http://${GATEWAY}:18080/                                 # from the sandbox
docker run --rm alpine wget -qO- http://${GATEWAY}:18080/     # from another container
```

## Running Multi-Line Scripts

For anything beyond a short one-liner, write the script to a file and copy it in — avoids quoting headaches:

```bash
cat > /tmp/job.py <<'EOF'
import pandas as pd
df = pd.read_csv('/data/input.csv')
print(df['value'].sum())
EOF

docker cp /tmp/job.py worker:/app/job.py
docker exec worker python /app/job.py
```

## Debugging

```bash
docker logs my-container         # stdout/stderr of a detached container
docker logs -f my-container      # stream in real time
docker exec -it my-container bash  # interactive shell
docker inspect my-container      # full config: network, mounts, env, ...
```

## Cleanup

```bash
docker rm -f my-container        # force stop + remove
docker network rm my-net         # remove custom networks
docker system prune              # remove stopped containers, dangling images, unused networks
```

## Common Recipes

### Clone a repo and run its tests

```bash
docker run -d --name test-env python:3.11 sleep infinity
docker exec test-env git clone https://github.com/owner/repo.git /testbed
docker exec test-env bash -c 'cd /testbed && git checkout <commit> && pip install -e .'
docker exec test-env bash -c 'cd /testbed && pytest tests/ -x'
mkdir -p /home/agent/results
docker cp test-env:/testbed/test-results/. /home/agent/results/
docker rm -f test-env
```

### Build a custom image and feed it host data

Because bind mounts don't work, you cannot `docker run -v /host/data:/data my-image`. Override the entrypoint, copy data in, then exec:

```bash
docker build -t my-tool /path/to/build/

docker run -d --name runner my-tool sleep infinity

docker exec runner mkdir -p /data
docker cp /home/agent/data/input.csv runner:/data/input.csv

docker exec runner python /app/process.py

mkdir -p /home/agent/output
docker cp runner:/data/result.txt /home/agent/output/

docker rm -f runner
```

### Build an image from an inline Dockerfile

```bash
mkdir -p /tmp/build
cat > /tmp/build/Dockerfile <<'EOF'
FROM python:3.11-slim
RUN pip install numpy pandas
WORKDIR /app
EOF
docker build -t my-py /tmp/build/
docker run --rm my-py python -c "import numpy, pandas; print(numpy.__version__)"
```

## Gotchas

### Bind mounts silently fail in both directions

`docker run -v /host/path:/container/path`:

- **Read direction**: your sandbox files do NOT appear in the container. Instead, Docker creates an empty directory at the source path on the DinD daemon's filesystem and mounts that. The `docker run` itself returns exit 0 — but your command inside the container sees empty dirs (or a file-mount becomes an empty directory, producing errors like `cat: read error: Is a directory`).

- **Write direction**: writes inside the bind-mounted path go to the DinD daemon's filesystem, not your sandbox. `ls` on the sandbox will show the source path unchanged.

**Use `docker cp` or named volumes instead.** Never rely on `-v <host>:<container>` for either reading or writing sandbox files.

### `localhost` inside a container is the container itself

To reach a port-published service from another container, use the DinD gateway IP, not `localhost`.

### Default bridge has no DNS

Containers on the default bridge cannot resolve each other by name — only by IP. Use a custom bridge network (`docker network create`) when you need name-based addressing.
