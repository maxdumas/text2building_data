#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# URLs obtained from here: https://www.businesslocationcenter.de/en/economic-atlas/download-portal/
urls=(
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Charlottenburg-Wilmersdorf.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Friedrichshain-Kreuzberg.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Lichtenberg.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Marzahn-Hellersdorf.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Mitte.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Neukoelln.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Pankow.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Reinickendorf.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Spandau.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Steglitz-Zehlendorf.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Tempelhof-Schoeneberg.zip"
    "https://s3.eu-central-1.amazonaws.com/dlportal-citygmldata/Treptow-Koepenick.zip"
)

cd citydata
mkdir -p berlin
cd berlin

for url in ${urls[@]}; do
    wget -qO- $url | busybox unzip - &
done

wait
