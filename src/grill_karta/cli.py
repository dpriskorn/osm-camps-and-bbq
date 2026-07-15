import click

from grill_karta.extract import extract_objects, get_pbf_path
from grill_karta.cluster import cluster_places, get_clusters_info
from grill_karta.gpx import to_gpx


@click.command()
@click.option("--download", is_flag=True, help="Ladda ner ny PBF från Geofabrik")
@click.option("--no-cache", is_flag=True, help="Ignorera cachad GeoJSON")
@click.option("--eps", default=100, help="DBSCAN epsilon i meter (default: 100)")
@click.option("--pbf", default="data/sweden-latest.osm.pbf", help="Sökväg till PBF-fil")
@click.option("--gpx", default=None, help="Output GPX-fil (default: grillplatser_{eps}m.gpx)")
def main(download, no_cache, eps, pbf, gpx):
    """
    Räkna unika grill- och rastplatser i Sverige med DBSCAN-klustring.

    Exempel:

      grillsok                     # Kör med cached data

      grillsok --download          # Ladda ner ny PBF

      grillsok --eps=50             # Testa med 50m radie
    """
    pbf_path = get_pbf_path(download=download)

    gdf = extract_objects(pbf_path, use_cache=not no_cache)

    gdf = cluster_places(gdf, eps_meters=eps)

    clusters_info = get_clusters_info(gdf)

    if gpx is None:
        gpx = f"grillplatser_{eps}m.gpx"

    gpx_content = to_gpx(gdf, clusters_info, eps)
    with open(gpx, "w") as f:
        f.write(gpx_content)

    click.echo(f"Skrev {len(clusters_info)} kluster till {gpx}")
    click.echo(f"  ({len(gdf)} punkter totalt)")


if __name__ == "__main__":
    main()
