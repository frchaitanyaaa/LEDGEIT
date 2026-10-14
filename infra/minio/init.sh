#!/bin/sh
# Create the evidence bucket with Object Lock (WORM) and a default GOVERNANCE retention.
set -e
mc alias set local http://minio:9000 ledgeit ledgeit123
if ! mc ls local/evidence >/dev/null 2>&1; then
  mc mb --with-lock local/evidence
  mc retention set --default GOVERNANCE 365d local/evidence
fi
echo "minio ready"
