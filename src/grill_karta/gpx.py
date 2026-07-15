import math
from collections import Counter
from datetime import datetime

import geopandas as gpd
from pyproj import Transformer


CRS_SWEREF = "EPSG:3006"
CRS_WGS84 = "EPSG:4326"


def project_to_sweref(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    transformer = Transformer.from_crs(CRS_WGS84, CRS_SWEREF, always_xy=True)
    gdf = gdf.copy()

    def transform_point(g):
        if hasattr(g, "x") and hasattr(g, "y"):
            x, y = transformer.transform(g.x, g.y)
            from shapely.geometry import Point
            return Point(x, y)
        if hasattr(g, "geoms"):
            from shapely.geometry import MultiPoint
            pts = [transform_point(p) for p in g.geoms]
            return MultiPoint(pts)
        return g

    gdf["geometry"] = gdf["geometry"].apply(transform_point)
    return gdf.set_crs(CRS_SWEREF)


def project_to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs and gdf.crs.to_epsg() == 4326:
        return gdf
    transformer = Transformer.from_crs(CRS_SWEREF, CRS_WGS84, always_xy=True)
    gdf = gdf.copy()

    def transform_point(g):
        if hasattr(g, "x") and hasattr(g, "y"):
            lon, lat = transformer.transform(g.x, g.y)
            from shapely.geometry import Point
            return Point(lon, lat)
        if hasattr(g, "geoms"):
            from shapely.geometry import MultiPoint
            pts = [transform_point(p) for p in g.geoms]
            return MultiPoint(pts)
        return g

    gdf["geometry"] = gdf["geometry"].apply(transform_point)
    return gdf.set_crs(CRS_WGS84)


def cluster_places(gdf: gpd.GeoDataFrame, eps_meters: int = 100) -> gpd.GeoDataFrame:
    gdf = project_to_sweref(gdf)
    coords = [(p.x, p.y) for p in gdf.geometry]
    db = DBSCAN(eps=eps_meters, min_samples=1).fit(coords)
    gdf["cluster"] = db.labels_
    return gdf


from sklearn.cluster import DBSCAN


def get_clusters_info(gdf: gpd.GeoDataFrame) -> list[dict]:
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
                "osm_type": row.get("osm_type", ""),
                "osm_id": row.get("osm_id", 0),
                "link": f"https://www.openstreetmap.org/{row.get('osm_type', '')}/{row.get('osm_id', '')}" if row.get("osm_id") else "",
            })
        info.append({
            "cluster": cid,
            "count": len(cluster),
            "centroid": centroid,
            "types": dict(counts),
            "members": members,
        })
    return info


def to_gpx(gdf: gpd.GeoDataFrame, clusters_info: list[dict], eps: int) -> str:
    gdf_wgs = project_to_wgs84(gdf.copy())
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
    gdf_centroids = project_to_wgs84(gdf_centroids)

    gdf_points = gdf_wgs.copy()
    gdf_points["cluster"] = gdf_points["cluster"].astype(str)
    gdf_points["type"] = gdf_points["_orig_type"]
    gdf_points["osm_link"] = gdf_points.apply(
        lambda r: f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}" if r.get("osm_id") else "",
        axis=1
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="grill-karta"',
        '     xmlns="http://www.topografix.com/GPX/1/1"',
        '     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        f'  <metadata>',
        f'    <name>Grillplatser i Sverige (DBSCAN eps={eps}m)</name>',
        f'    <time>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}</time>',
        f'  </metadata>',
    ]

    for _, row in gdf_centroids.iterrows():
        lines.append(f'  <wpt lat="{row.geometry.y:.7f}" lon="{row.geometry.x:.7f}">')
        lines.append(f'    <name>{row["cluster"]}</name>')
        lines.append(f'    <desc>{row["count"]} objekt: {row["types"]}</desc>')
        lines.append(f'    <type>cluster</type>')
        lines.append('  </wpt>')

    for _, row in gdf_points.iterrows():
        lines.append(f'  <wpt lat="{row.geometry.y:.7f}" lon="{row.geometry.x:.7f}">')
        lines.append(f'    <name>{row["cluster"]}_{row["type"]}</name>')
        lines.append(f'    <desc>{row["osm_link"]}</desc>')
        lines.append(f'    <type>point</type>')
        lines.append('  </wpt>')

    lines.append('</gpx>')
    return "\n".join(lines)
