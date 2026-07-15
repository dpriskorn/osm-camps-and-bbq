# Grill-karta

Räkna unika grill- och rastplatser i Sverige med DBSCAN-klustring.

## Installera

```bash
uv sync
```

## Hämta data

```bash
./scripts/fetch_pbf.sh
```

## Kör

```bash
uv run grillsok --download   # Första gången: ladda ner PBF
uv run grillsok --eps=75      # Testa med 75m radie
uv run grillsok --no-cache    # Ignorera cache
```

## Output

`grillplatser_{eps}m.gpx` med:
- **Waypoints för kluster-centroider** - `name=Plats #N`, `desc=Antal objekt + typer`
- **Waypoints för alla punkter** - `desc=OSM-länk` till varje objekt

## Filtrering

Inkluderar:
- `amenity=bbq`
- `leisure=firepit`
- `amenity=shelter` + `shelter_type=lean_to`
- `amenity=shelter` + `shelter_type=camp_site`

## Verktyg

- **osmium-tool** - filtrera och exportera OSM-data
- **geopandas** - läs GeoJSON
- **scikit-learn** - DBSCAN-klustring
- **pyproj** - projektion till SWEREF99 TM (EPSG:3006)
