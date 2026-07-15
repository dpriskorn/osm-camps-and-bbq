from collections import Counter

import geopandas as gpd
from sklearn.cluster import DBSCAN


CRS_SWEREF = "EPSG:3006"
CRS_WGS84 = "EPSG:4326"


def project_to_sweref(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    if gdf.crs.to_epsg() != 3006:
        gdf = gdf.to_crs(CRS_SWEREF)
    return gdf


def cluster_places(gdf: gpd.GeoDataFrame, eps_meters: int = 100) -> gpd.GeoDataFrame:
    gdf = project_to_sweref(gdf)

    coords = [(p.x, p.y) for p in gdf.geometry]

    db = DBSCAN(eps=eps_meters, min_samples=1).fit(coords)
    gdf["cluster"] = db.labels_

    return gdf


def get_osm_link(row) -> str:
    osm_type = row.get("osm_type", "")
    osm_id = row.get("osm_id", "")
    if osm_type and osm_id:
        return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    obj_id = row.get("id", "")
    if obj_id.startswith("n"):
        return f"https://www.openstreetmap.org/node/{obj_id[1:]}"
    if obj_id.startswith("w"):
        return f"https://www.openstreetmap.org/way/{obj_id[1:]}"
    if obj_id.startswith("r"):
        return f"https://www.openstreetmap.org/relation/{obj_id[1:]}"
    return ""


def parse_osm_id(row):
    obj_id = str(row.get("id", ""))
    if obj_id.startswith("n"):
        return "node", int(obj_id[1:])
    if obj_id.startswith("w"):
        return "way", int(obj_id[1:])
    if obj_id.startswith("r"):
        return "relation", int(obj_id[1:])
    return "", 0


def build_place_info(gdf: gpd.GeoDataFrame, cluster_id: int) -> dict:
    cluster = gdf[gdf["cluster"] == cluster_id]
    centroid = cluster.unary_union.centroid

    counts = Counter(cluster.get("type", cluster.get("_orig_type", "")))
    members = []
    for _, row in cluster.iterrows():
        osm_type, osm_id = parse_osm_id(row)
        link = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else ""
        members.append({
            "type": row.get("type", row.get("_orig_type", "")),
            "name": row.get("name", ""),
            "osm_type": osm_type,
            "osm_id": osm_id,
            "link": link,
        })

    return {
        "cluster": cluster_id,
        "count": len(cluster),
        "centroid": centroid,
        "types": dict(counts),
        "members": members,
    }


def get_clusters_info(gdf: gpd.GeoDataFrame) -> list[dict]:
    unique_clusters = sorted(gdf["cluster"].unique())
    return [build_place_info(gdf, cid) for cid in unique_clusters]


def gdf_from_clusters_info(info: list[dict]) -> gpd.GeoDataFrame:
    records = []
    for place in info:
        centroid = place["centroid"]
        type_str = ", ".join(f"{n}x {t}" for t, n in place["types"].items())
        links = "\n".join(m["link"] for m in place["members"] if m["link"])
        records.append({
            "name": f"Plats #{place['cluster']}",
            "desc": f"{place['count']} objekt: {type_str}\n{links}",
            "lat": centroid.y,
            "lon": centroid.x,
            "cluster": place["cluster"],
            "count": place["count"],
        })
    return gpd.GeoDataFrame(records, geometry=gpd.points_from_xy([r["lon"] for r in records], [r["lat"] for r in records]), crs=CRS_SWEREF)
