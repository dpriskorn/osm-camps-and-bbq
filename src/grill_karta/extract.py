import subprocess
import tempfile
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


TAGS = [
    "amenity=bbq",
    "leisure=firepit",
    "amenity=shelter",
]

SWEDEN_PBF = "../data/sweden-latest.osm.pbf"
GRILLS_GEOJSON = "data/grills.geojson"


def get_pbf_path(download: bool = False) -> str:
    path = Path(SWEDEN_PBF)
    if path.exists():
        return str(path)
    if download:
        raise SystemExit(
            f"Hittar inte {path}. "
            "Kör fetch_pbf.sh eller ladda ner manuellt från Geofabrik."
        )
    raise SystemExit(
        f"Hittar inte {path}. "
        "Kör med --download eller ./scripts/fetch_pbf.sh"
    )


def extract_objects(pbf_path: str, use_cache: bool = True) -> gpd.GeoDataFrame:
    if use_cache and Path(GRILLS_GEOJSON).exists():
        print(f"Läser från cache: {GRILLS_GEOJSON}")
        return gpd.read_file(GRILLS_GEOJSON)

    tmpdir = tempfile.mkdtemp()
    try:
        filtered_pbf = os.path.join(tmpdir, "filtered.pbf")
        geojson_path = os.path.join(tmpdir, "grills.geojson")

        print("Filtrerar objekt med osmium...")
        subprocess.run(
            [
                "osmium", "tags-filter",
                pbf_path,
                "-o", filtered_pbf,
                "--",
                "amenity=bbq",
                "leisure=firepit",
                "amenity=shelter",
            ],
            check=True,
            capture_output=True,
        )

        print("Exporterar till GeoJSON...")
        subprocess.run(
            [
                "osmium", "export",
                filtered_pbf,
                "-o", geojson_path,
                "--geometry-types=point,linestring,polygon",
                "--add-unique-id=type_id",
                "-f", "geojson",
            ],
            check=True,
            capture_output=True,
        )

        print("Läser in GeoJSON...")
        gdf = gpd.read_file(geojson_path)

    finally:
        import shutil
        shutil.rmtree(tmpdir)

    gdf = _normalize(gdf)
    gdf = _filter_types(gdf)
    gdf = _filter_private(gdf)
    gdf = _to_centroids(gdf)
    gdf = _parse_osm_id(gdf)

    Path(GRILLS_GEOJSON).parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(GRILLS_GEOJSON, driver="GeoJSON")
    print(f"Sparade {len(gdf)} objekt till {GRILLS_GEOJSON}")

    return gdf


def _normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if "tags" in gdf.columns:
        tags_df = gdf["tags"].apply(pd.Series)
        for col in tags_df.columns:
            if col not in gdf.columns:
                gdf[col] = tags_df[col]

    gdf["_orig_type"] = ""

    if "leisure" in gdf.columns:
        mask = gdf["leisure"] == "firepit"
        gdf.loc[mask, "_orig_type"] = "firepit"
        gdf.loc[mask, "type"] = "firepit"

    if "amenity" in gdf.columns:
        mask = gdf["amenity"].isin(["bbq", "shelter"])
        gdf.loc[mask, "_orig_type"] = gdf.loc[mask, "amenity"]
        gdf.loc[mask, "type"] = gdf.loc[mask, "amenity"]

    gdf["type"] = gdf.get("type", "")
    return gdf


def _filter_types(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    shelter_types = gdf.get("shelter_type", pd.Series([""] * len(gdf)))

    return gdf[
        (gdf["_orig_type"] == "bbq") |
        (gdf["_orig_type"] == "firepit") |
        (
            (gdf["_orig_type"] == "shelter") &
            shelter_types == "lean_to"
        )
    ].copy()


def _filter_private(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf[gdf.get("access", "") != "private"].copy()


def _to_centroids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    def to_centroid(g):
        if hasattr(g, "centroid"):
            return g.centroid
        return g

    gdf["geometry"] = gdf["geometry"].apply(to_centroid)
    return gdf


def _parse_osm_id(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    def parse(id_str):
        id_str = str(id_str)
        if id_str.startswith("n"):
            return ("node", int(id_str[1:]))
        if id_str.startswith("w"):
            return ("way", int(id_str[1:]))
        if id_str.startswith("r"):
            return ("relation", int(id_str[1:]))
        return ("", 0)

    parsed = gdf["id"].apply(parse)
    gdf["osm_type"] = [p[0] for p in parsed]
    gdf["osm_id"] = [p[1] for p in parsed]
    return gdf


def load_cached() -> gpd.GeoDataFrame:
    if Path(GRILLS_GEOJSON).exists():
        return gpd.read_file(GRILLS_GEOJSON)
    raise SystemExit(
        f"Ingen cached data ({GRILLS_GEOJSON}). "
        "Kör utan --no-cache."
    )
