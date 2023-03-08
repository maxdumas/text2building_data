#!/bin/bash

docker run --rm -v $(pwd)/citydata:/data citygml4j/citygml-tools to-cityjson /data/berlin/*/*.gml