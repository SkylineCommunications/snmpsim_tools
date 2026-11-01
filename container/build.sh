#!/usr/bin/env bash
# Build an snmpsim image with Podman for one simulation file (any name, as long as it is inside this folder).
# Inside the image the file is always named public.snmprec, so the agent answers to the SNMP community "public".
#
# Usage:
#   ./build.sh <simulation-file> <image-name>
#
# Examples:
#   ./build.sh data/cmts01.snmprec cmts01                        -> localhost/cmts01:latest
#   ./build.sh data/my-device.snmprec snmpsim/my-device:1.0      -> localhost/snmpsim/my-device:1.0
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <simulation-file> <image-name>" >&2
    exit 1
fi

file="$1"
image="$2"
context_dir="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$file" || "$file" != *.snmprec ]]; then
    echo "ERROR: '$file' is not an existing .snmprec file" >&2
    exit 1
fi

# COPY only sees files inside the build context (this folder), so pass the path relative to it
relative_file="$(realpath --relative-to="$context_dir" -- "$file")"
if [[ "$relative_file" == ../* ]]; then
    echo "ERROR: '$file' must be inside $context_dir (e.g. in data/)" >&2
    exit 1
fi

podman build --file "$context_dir/Containerfile" --build-arg SIMULATION_FILE="$relative_file" --tag "$image" "$context_dir"
echo "Built $image from $relative_file (SNMP community: public)"
