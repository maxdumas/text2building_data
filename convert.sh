#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

gml_path="$1"
gml_dir=$(dirname "$1")
gml_name=$(basename "$1")

docker run --rm -v $gml_dir:/data citygml4j/citygml-tools to-cityjson /data/$gml_name
