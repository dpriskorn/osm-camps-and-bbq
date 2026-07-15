import subprocess
import tempfile
import os
from pathlib import Path
from datetime import date

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


PBF_PATH = "/home/nizo/src/python/data/sweden-latest.osm.pbf"
OUTPUT_GPX = f"output/wilderness_huts_sweden_{date.today().strftime('%Y%m%d')}.gpx"


def filter_wilderness_huts():
    tmpdir = tempfile.mkdtemp()
    try:
        huts_pbf = os.path.join(tmpdir, "wilderness_huts.pbf")
        huts_geojson = os.path.join(tmpdir, "wilderness_huts.geojson")

        print("Filtering wilderness huts...")
        subprocess.run(
            [
                "osmium", "tags-filter",
                PBF_PATH,
                "-o", huts_pbf,
                "--overwrite",
                "--",
                "tourism=wilderness_hut",
            ],
            check=True,
            capture_output=True,
        )

        print("Exporting to GeoJSON...")
        subprocess.run(
            [
                "osmium", "export",
                huts_pbf,
                "-o", huts_geojson,
                "--geometry-types=point,polygon",
                "--add-unique-id=type_id",
                "-f", "geojson",
            ],
            check=True,
            capture_output=True,
        )

        print("Reading GeoJSON...")
        gdf = gpd.read_file(huts_geojson)
        print(f"  Total wilderness huts: {len(gdf)}")

        if "access" in gdf.columns:
            gdf = gdf[gdf["access"] != "private"].copy()
            print(f"  After filtering access!=private: {len(gdf)}")

        def to_point_geom(g):
            if hasattr(g, "centroid"):
                return g.centroid
            return g

        gdf["geometry"] = gdf["geometry"].apply(to_point_geom)

        write_gpx(gdf)

    finally:
        import shutil
        shutil.rmtree(tmpdir)


def parse_osm_id(id_str):
    id_str = str(id_str)
    if id_str.startswith("n"):
        return ("node", int(id_str[1:]))
    if id_str.startswith("w"):
        return ("way", int(id_str[1:]))
    if id_str.startswith("r"):
        return ("relation", int(id_str[1:]))
    return ("", 0)


def write_gpx(gdf):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="wilderness-huts-exporter"',
        '     xmlns="http://www.topografix.com/GPX/1/1"',
        '     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        '  <metadata>',
        '    <name>Wilderness huts in Sweden</name>',
        '  </metadata>',
    ]

    for _, row in gdf.iterrows():
        lat = row.geometry.y
        lon = row.geometry.x
        osm_type, osm_id = parse_osm_id(row.get("id", ""))
        link = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else ""
        name = row.get("name", "")
        if pd.isna(name) or not name or str(name) == "nan":
            name = f"{osm_type}_{osm_id}" if osm_id else "Wilderness Hut"

        lines.append(f'  <wpt lat="{lat:.7f}" lon="{lon:.7f}">')
        lines.append(f'    <name>{name}</name>')
        if link:
            lines.append(f'    <desc>{link}</desc>')
        lines.append('  </wpt>')

    lines.append('</gpx>')

    Path(OUTPUT_GPX).parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    with open(OUTPUT_GPX, "w") as f:
        f.write(content)

    print(f"Wrote {len(gdf)} wilderness huts to {OUTPUT_GPX}")


if __name__ == "__main__":
    filter_wilderness_huts()
