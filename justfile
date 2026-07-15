# Hämtningar
fetch:
    ./scripts/fetch_pbf.sh

# Kör med valfri epsilon (default 100m)
run eps="100":
    uv run grillsok --eps {{eps}}

# Hjälp
help:
    uv run grillsok --help

# Rensa cache
clean:
    rm -f data/grills.geojson grillplatser_*.gpx

# Installera dependencies
install:
    uv sync
