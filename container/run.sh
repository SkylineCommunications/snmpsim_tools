#!/usr/bin/env bash
# Run an snmpsim image (built with build.sh) with Podman.
#
# Usage:
#   ./run.sh                          run image DEVICE_NAME on host UDP port PORT (both from .env)
#   ./run.sh <image-name> [port]      e.g. ./run.sh snmpsim/my-device:1.0 10162
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .env ]]; then
    # shellcheck source=/dev/null
    source <(tr -d '\r' < .env)
fi

image="${1:-${DEVICE_NAME:?pass an image name or set DEVICE_NAME in .env}}"
port="${2:-${PORT:?pass a port or set PORT in .env}}"

# Container name based on the image name without registry, path and tag: snmpsim/my-device:1.0 -> snmpsim_my-device
name="${image##*/}"
container="snmpsim_${name%%[:@]*}"

if ! podman image exists "$image"; then
    echo "ERROR: image $image not found, build it first with: ./build.sh <simulation-file> $image" >&2
    exit 1
fi

# --replace removes an existing container with the same name first.
# The agent listens on 1161/udp inside the container (see Containerfile).
podman run --detach --replace --name "$container" --publish "${port}:1161/udp" "$image"

cat <<EOF
Started $container ($image) on UDP port $port
  Test: snmpget -v2c -c public localhost:$port 1.3.6.1.2.1.1.1.0
  Logs: podman logs -f $container
  Stop: podman rm -f $container
EOF
