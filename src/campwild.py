import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import re
from datetime import datetime
from collections import Counter

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from cluster import cluster_places, get_clusters_info, CRS_SWEREF, CRS_WGS84


SWEDEN_BOUNDS = {
    "lat_min": 55.0,
    "lat_max": 71.0,
    "lon_min": 10.0,
    "lon_max": 25.0,
}


def parse_campwild_gpx(gpx_path: str) -> gpd.GeoDataFrame:
    import xml.etree.ElementTree as ET

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

    records = []
    for wpt in root.findall("gpx:wpt", ns):
        lat = float(wpt.get("lat"))
        lon = float(wpt.get("lon"))

        name_el = wpt.find("gpx:name", ns)
        name = name_el.text if name_el is not None else ""

        desc_el = wpt.find("gpx:desc", ns)
        desc = desc_el.text if desc_el is not None and desc_el.text else ""

        link_el = wpt.find("gpx:link", ns)
        link = link_el.get("href") if link_el is not None else ""

        camp_type = ""
        if desc and "Lean To" in desc:
            camp_type = "lean_to"
        elif "Tower" in desc:
            camp_type = "tower"
        elif "Hut" in desc:
            camp_type = "hut"
        elif "Basic Shelter" in desc:
            camp_type = "basic_shelter"
        elif "Campsite" in desc:
            camp_type = "campsite"
        else:
            camp_type = "unknown"

        records.append({
            "name": name,
            "desc": desc,
            "link": link,
            "type": camp_type,
            "_orig_type": camp_type,
            "geometry": Point(lon, lat),
        })

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_WGS84)
    return gdf


def filter_sweden(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf_wgs = gdf.to_crs(CRS_WGS84)
    lats = gdf_wgs.geometry.y
    lons = gdf_wgs.geometry.x

    mask = (
        (lats >= SWEDEN_BOUNDS["lat_min"]) &
        (lats <= SWEDEN_BOUNDS["lat_max"]) &
        (lons >= SWEDEN_BOUNDS["lon_min"]) &
        (lons <= SWEDEN_BOUNDS["lon_max"])
    )
    return gdf[mask].copy()


def get_campwild_clusters_info(gdf: gpd.GeoDataFrame) -> list[dict]:
    unique_clusters = sorted(gdf["cluster"].unique())
    info = []
    for cid in unique_clusters:
        cluster = gdf[gdf["cluster"] == cid]
        centroid = cluster.unary_union.centroid
        counts = Counter(cluster["_orig_type"])
        members = []
        for _, row in cluster.iterrows():
            members.append({
                "type": row.get("_orig_type", ""),
                "name": row.get("name", ""),
                "link": row.get("link", ""),
            })
        info.append({
            "cluster": cid,
            "count": len(cluster),
            "centroid": centroid,
            "types": dict(counts),
            "members": members,
        })
    return info


def to_campwild_gpx(gdf: gpd.GeoDataFrame, clusters_info: list[dict], eps: int) -> str:
    gdf_wgs = gdf.to_crs(CRS_WGS84)

    gdf_centroids = gpd.GeoDataFrame(
        [{
            "cluster": p["cluster"],
            "count": p["count"],
            "types": ", ".join(f"{n}x {t}" for t, n in p["types"].items()),
            "links": "\n".join(m["link"] for m in p["members"] if m["link"]),
            "geometry": p["centroid"],
        } for p in clusters_info],
        geometry="geometry",
        crs=CRS_SWEREF,
    )
    gdf_centroids = gdf_centroids.to_crs(CRS_WGS84)

    gdf_points = gdf_wgs.copy()
    gdf_points["cluster"] = gdf_points["cluster"].astype(str)
    gdf_points["type"] = gdf_points["_orig_type"]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="campwild-karta"',
        '     xmlns="http://www.topografix.com/GPX/1/1"',
        '     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        f'  <metadata>',
        f'    <name>CampWild platser i Sverige (DBSCAN eps={eps}m)</name>',
        f'    <time>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}</time>',
        f'  </metadata>',
    ]

    for _, row in gdf_centroids.iterrows():
        lines.append(f'  <wpt lat="{row.geometry.y:.7f}" lon="{row.geometry.x:.7f}">')
        lines.append(f'    <name>{row["cluster"]}</name>')
        lines.append(f'    <desc>{row["count"]} objekt: {row["types"]}\n{row["links"]}</desc>')
        lines.append(f'    <type>cluster</type>')
        lines.append('  </wpt>')

    for _, row in gdf_points.iterrows():
        lines.append(f'  <wpt lat="{row.geometry.y:.7f}" lon="{row.geometry.x:.7f}">')
        lines.append(f'    <name>{row["cluster"]}_{row["type"]}</name>')
        lines.append(f'    <desc>{row["link"]}</desc>')
        lines.append(f'    <type>point</type>')
        lines.append('  </wpt>')

    lines.append('</gpx>')
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analysera CampWild platser i Sverige")
    parser.add_argument("--gpx", default="data/campwild-2026-07-15.gpx", help="CampWild GPX-fil")
    parser.add_argument("--eps", type=int, default=100, help="DBSCAN epsilon i meter (default: 100)")
    parser.add_argument("--output", default=None, help="Output GPX-fil")
    args = parser.parse_args()

    gdf = parse_campwild_gpx(args.gpx)
    print(f"Laddade {len(gdf)} platser från GPX")

    gdf_sweden = filter_sweden(gdf)
    print(f"Filterade till {len(gdf_sweden)} platser i Sverige")

    gdf_clustered = cluster_places(gdf_sweden, eps_meters=args.eps)
    clusters_info = get_campwild_clusters_info(gdf_clustered)

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d")
        n_clusters = len(clusters_info)
        n_points = len(gdf_clustered)
        args.output = f"output/campwild_{args.eps}m_{n_clusters}_kluster_av_{n_points}_punkter_{ts}.gpx"

    gpx_content = to_campwild_gpx(gdf_clustered, clusters_info, args.eps)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(gpx_content)

    print(f"Skrev {len(clusters_info)} kluster till {args.output}")
    print(f"  ({len(gdf_clustered)} punkter totalt)")


if __name__ == "__main__":
    main()
