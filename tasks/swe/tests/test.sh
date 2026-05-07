#!/bin/bash
# Collect agent-produced files into /logs/artifacts/
mkdir -p /logs/artifacts

if [ -d /home/agent/submission ]; then
    cp -r /home/agent/submission /logs/artifacts/submission
fi

find /home/agent -maxdepth 1 -not -name "resources" -not -path "/home/agent" \
    -exec cp -r {} /logs/artifacts/ \; 2>/dev/null || true

# Minimal completeness check: submission must contain run_pipeline.sh
if [ ! -f /home/agent/submission/run_pipeline.sh ]; then
    echo "0.0" > /logs/verifier/reward.txt
    exit 0
fi

echo "1.0" > /logs/verifier/reward.txt
