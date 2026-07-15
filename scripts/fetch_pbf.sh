#!/bin/bash
set -e

DATA_DIR="data"
PBF_FILE="$DATA_DIR/sweden-latest.osm.pbf"
URL="https://download.geofabrik.de/europe/sweden-latest.osm.pbf"

mkdir -p "$DATA_DIR"

if [ -f "$PBF_FILE" ]; then
    echo "PBF finns redan: $PBF_FILE"
    read -p "Vill du ladda ner pnytt? [y/N] " confirm
    if [ "$confirm" != "y" ]; then
        echo "Avbryter."
        exit 0
    fi
fi

echo "Laddar ner Sveriges PBF från Geofabrik..."
curl -L -o "$PBF_FILE" "$URL"

echo "Klar: $PBF_FILE"
