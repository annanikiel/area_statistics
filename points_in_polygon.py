"""
Step 1: work out which Output Areas make up a bespoke area (e.g. a parish).

Given a digitised boundary, this finds every ONS Output Area whose population
weighted centroid falls inside it, and writes that list out for step 2
(data_aggregates.py) to use.

*** How it works ***

  1. Read the boundary and reproject it to EPSG:27700 (the Ordnance Survey /
     ONS projection this project uses throughout).
  2. Take the bounding box of the boundary and widen it by a buffer.
  3. Ask the ONS Open Geography Portal for the OA centroids in that box.
     Only that handful is downloaded, not the ~190,000-point national file.
  4. Test each of those centroids against the boundary itself.
  5. Write the result as JSON (for reference) and CSV (the lookup table that
     step 2 consumes), plus a map so you can eyeball that it worked.

*** A word about projections ***

Points and polygon must be in the same projection for the matching to work.
EPSG:27700 is used here because it is what ONS publishes in and because it
measures in metres, which makes the buffer easy to reason about. The source
projection of your boundary is read from the file where it is declared, and
guessed from the coordinates otherwise.

*** How to run ***

    python3 points_in_polygon.py

Settings come from variables_pip.py - see variables_examples/ for a template.
"""

import csv
import json
import os

import pyproj
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union
from shapely import force_2d

import census_api


############################################################
# 1. Settings that rarely change
############################################################

# The projection everything is converted into before matching.
TARGET_CRS = "EPSG:27700"

# How far beyond the boundary's bounding box to look for centroids, in metres.
# This only widens the shortlist - the real test is still the boundary itself -
# so a generous value costs very little.
DEFAULT_BUFFER_M = 300

# Which GeoJSON property maps to which output column. The defaults match the
# parish boundary files used in this project; adjust if yours differ.
PROPERTY_MAP = {
    "id": "ParishID",
    "name": "Name",
    "loc": "Location",
    "dean": "Deanery",
}


############################################################
# 2. Reading the boundary
############################################################

def detect_crs(data):
    """
    Work out what projection a GeoJSON file is in.

    Tried in order:
      1. A 'crs' member in the file (older GeoJSON exports include one).
      2. A guess from the size of the coordinates.
      3. EPSG:4326, which the GeoJSON standard says to assume.

    Returns:
        str: e.g. 'EPSG:3857'
    """
    # 1. Declared in the file?
    crs = data.get("crs")
    if isinstance(crs, dict):
        name = (crs.get("properties") or {}).get("name", "")
        # Names look like 'urn:ogc:def:crs:EPSG::3857' or 'EPSG:3857'
        if "EPSG" in str(name):
            code = str(name).replace(":", " ").split()[-1]
            if code.isdigit():
                return f"EPSG:{code}"

    # 2. Guess from the magnitude of the first coordinate.
    node = data["features"][0]["geometry"]["coordinates"]
    while isinstance(node, list) and node and isinstance(node[0], list):
        node = node[0]
    x, y = abs(node[0]), abs(node[1])

    if x <= 180 and y <= 90:
        return "EPSG:4326"          # degrees
    if x <= 700000 and y <= 1300000:
        return "EPSG:27700"         # British National Grid, in metres
    return "EPSG:3857"              # Web Mercator, in much larger metres


def load_boundary(path, source_crs=None, target_crs=TARGET_CRS):
    """
    Load a boundary file and return it as a Shapely geometry in target_crs.

    Handles Polygon and MultiPolygon, boundaries with holes, files with several
    features, and coordinates that carry an elevation value.

    Args:
        path (str): Path to the GeoJSON file.
        source_crs (str): Override the file's projection, e.g. 'EPSG:3857'.
        target_crs (str): Projection to convert into.

    Returns:
        tuple: (geometry, properties dict from the first feature)
    """
    with open(path) as handle:
        data = json.load(handle)

    features = data.get("features")
    if not features:
        raise ValueError(f"No features found in {path}")

    # Shapely understands GeoJSON geometry directly, so there is no need to
    # walk the nested coordinate lists by hand. This is what makes holes and
    # multi-part boundaries work.
    geometries = [shape(feature["geometry"]) for feature in features]
    geometry = unary_union(geometries) if len(geometries) > 1 else geometries[0]

    # Boundaries exported from 3D tools carry a height on every coordinate.
    # Drop it - we are matching in two dimensions.
    if geometry.has_z:
        geometry = force_2d(geometry)

    # Fix self-intersections, which would otherwise make 'contains' unreliable.
    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    source_crs = source_crs or detect_crs(data)
    if source_crs != target_crs:
        # Build the transformer once and reuse it, rather than per coordinate.
        project = pyproj.Transformer.from_crs(
            pyproj.CRS(source_crs), pyproj.CRS(target_crs), always_xy=True
        ).transform
        geometry = transform(project, geometry)

    properties = features[0].get("properties", {}) or {}
    return geometry, properties


def buffered_bounds(geometry, buffer_m=DEFAULT_BUFFER_M):
    """
    Return the geometry's bounding box widened by buffer_m on every side.

    Note the signs: the minimum corner moves down and left, the maximum corner
    moves up and right. Adding the buffer to all four would slide the box
    diagonally instead of growing it, and could drop points near the
    south-western edge.
    """
    minx, miny, maxx, maxy = geometry.bounds
    return (minx - buffer_m, miny - buffer_m, maxx + buffer_m, maxy + buffer_m)


############################################################
# 3. The matching itself
############################################################

def find_oas_in_area(geometry, year="2021", buffer_m=DEFAULT_BUFFER_M,
                     centroids=None):
    """
    Find the Output Areas whose centroid lies inside the boundary.

    Args:
        geometry: Boundary as a Shapely geometry in EPSG:27700.
        year (str): Census year - '2021', '2011' or '2001'.
        buffer_m (int): Bounding-box buffer in metres.
        centroids (list): Supply [[code, x, y], ...] to skip the API call
            (used by the tests, and if you prefer a local centroids file).

    Returns:
        tuple: (inside, outside) - two lists of [code, x, y]. 'outside' holds
        the centroids that were in the box but not in the boundary, which is
        what the sense-check map draws in grey.
    """
    if centroids is None:
        centroids = census_api.fetch_oa_centroids(
            buffered_bounds(geometry, buffer_m), year=year
        )

    inside, outside = [], []
    for code, x, y in centroids:
        if geometry.contains(Point(x, y)):
            inside.append([code, x, y])
        else:
            outside.append([code, x, y])

    return inside, outside


############################################################
# 3b. Several areas in one file
############################################################

def load_boundaries(path, source_crs=None, target_crs=TARGET_CRS):
    """
    Load a boundary file where each feature is a separate area.

    Where load_boundary() merges everything into one shape, this keeps the
    features apart - one per parish - so a whole diocese can be processed in
    a single run.

    Returns:
        list: [(geometry, properties), ...] in target_crs.
    """
    with open(path) as handle:
        data = json.load(handle)

    features = data.get("features")
    if not features:
        raise ValueError(f"No features found in {path}")

    source_crs = source_crs or detect_crs(data)
    project = None
    if source_crs != target_crs:
        project = pyproj.Transformer.from_crs(
            pyproj.CRS(source_crs), pyproj.CRS(target_crs), always_xy=True
        ).transform

    areas = []
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.has_z:
            geometry = force_2d(geometry)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if project is not None:
            geometry = transform(project, geometry)
        areas.append((geometry, feature.get("properties", {}) or {}))

    return areas


def match_all_areas(areas, year="2021", buffer_m=DEFAULT_BUFFER_M,
                    centroids=None):
    """
    Match Output Areas to every area in one pass.

    The centroids are downloaded once for the combined extent of all the
    areas, then each area is tested against that one set. For a diocese this
    is far quicker than fetching per parish.

    Args:
        areas (list): [(geometry, properties), ...] from load_boundaries.
        year (str): Census year.
        buffer_m (int): Bounding-box buffer in metres.
        centroids (list): Supply [[code, x, y], ...] to skip the API call.

    Returns:
        tuple: (matches, report)
            matches - [{'OA', 'x', 'y', **properties}, ...]
            report  - counts, plus any OA claimed by more than one area.
    """
    if centroids is None:
        # One box covering everything, then one download.
        boxes = [buffered_bounds(geometry, buffer_m) for geometry, _ in areas]
        combined = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                    max(b[2] for b in boxes), max(b[3] for b in boxes))
        centroids = census_api.fetch_oa_centroids(combined, year=year)

    matches = []
    claimed = {}          # OA code -> list of areas that contain it
    per_area = {}

    for geometry, properties in areas:
        label = properties.get("id") or properties.get("name") or len(per_area)
        # Testing the bounding box first is much cheaper than the full
        # geometry, and skips most centroids straight away.
        minx, miny, maxx, maxy = geometry.bounds
        count = 0
        for code, x, y in centroids:
            if not (minx <= x <= maxx and miny <= y <= maxy):
                continue
            if geometry.contains(Point(x, y)):
                matches.append({"OA": code, "x": x, "y": y, **properties})
                claimed.setdefault(code, []).append(label)
                count += 1
        per_area[label] = count

    overlaps = {code: owners for code, owners in claimed.items()
                if len(owners) > 1}

    report = {
        "areas": len(areas),
        "centroids_searched": len(centroids),
        "matched": len(claimed),
        "rows": len(matches),
        "per_area": per_area,
        "empty_areas": [label for label, n in per_area.items() if n == 0],
        "overlaps": overlaps,
    }
    return matches, report


def write_combined_lookup(matches, csv_path, property_map=None):
    """
    Write the lookup covering every area, for step 2 to aggregate.

    One row per Output Area per area that claims it.
    """
    property_map = property_map or PROPERTY_MAP
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

    # Keep only the properties that are actually present, in a stable order.
    present = [key for key in property_map if any(key in m for m in matches)]
    columns = ["OA"] + [property_map[key] for key in present]

    with open(csv_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for match in matches:
            writer.writerow([match["OA"]] + [match.get(key, "") for key in present])

    return columns


############################################################
# 4. Writing the results out
############################################################

def write_outputs(inside, properties, json_path=None, csv_path=None,
                  property_map=None):
    """
    Write the matched OA list to disk.

    Two formats, because they serve different purposes:

      * JSON - the OA list with its coordinates and the parish details, handy
        for reference or for feeding another script.
      * CSV  - the lookup table step 2 needs: one row per OA, carrying the
        parish and deanery it belongs to. Because the parish details come from
        the boundary file's own properties, this is built for you.

    To cover a whole diocese, run this once per parish and concatenate the CSVs.
    """
    property_map = property_map or PROPERTY_MAP
    # Only map across properties the file actually has.
    parish = {
        column: properties[key]
        for key, column in property_map.items()
        if key in properties
    }

    if json_path:
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w") as handle:
            json.dump(
                {"parish": parish, "count": len(inside),
                 "output_areas": [{"OA": c, "x": x, "y": y} for c, x, y in inside]},
                handle, indent=2,
            )

    if csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        columns = ["OA"] + list(parish.keys())
        with open(csv_path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            for code, _x, _y in inside:
                writer.writerow([code] + [parish[c] for c in columns[1:]])

    return parish


############################################################
# 5. Sense-check map
############################################################

def make_sense_check_map(geometry, inside, outside, path,
                         source_crs=TARGET_CRS):
    """
    Draw the boundary and the centroids so you can see the match worked.

    Green markers are the OAs that were matched, grey ones were searched but
    fell outside. If the green markers do not fill the shape, something has
    gone wrong - most likely the projection.

    Folium works in latitude/longitude, so everything is converted back to
    EPSG:4326 for display only.
    """
    import folium

    to_wgs84 = pyproj.Transformer.from_crs(
        pyproj.CRS(source_crs), pyproj.CRS("EPSG:4326"), always_xy=True
    ).transform

    outline = transform(to_wgs84, geometry)
    centre = outline.centroid

    # OpenStreetMap tiles need no API key, so the map works out of the box.
    area_map = folium.Map(location=[centre.y, centre.x], zoom_start=14,
                          tiles="OpenStreetMap")

    folium.GeoJson(
        outline.__geo_interface__,
        name="Boundary",
        style_function=lambda _: {"color": "#2b6cb0", "weight": 3,
                                  "fillOpacity": 0.08},
    ).add_to(area_map)

    for label, points, colour in [("Outside", outside, "#9aa5b1"),
                                  ("Inside", inside, "#2f855a")]:
        layer = folium.FeatureGroup(name=f"{label} ({len(points)})")
        for code, x, y in points:
            lon, lat = to_wgs84(x, y)
            folium.CircleMarker(
                location=[lat, lon], radius=4, color=colour, weight=1,
                fill=True, fill_opacity=0.9, tooltip=f"{code} ({label.lower()})",
            ).add_to(layer)
        layer.add_to(area_map)

    folium.LayerControl().add_to(area_map)
    area_map.save(path)
    return path


############################################################
# 6. Running it
############################################################

def main():
    # Imported here so the functions above can be used (and tested) without a
    # variables_pip.py being present.
    from variables_pip import polygon_p, oa_json_output, oa_csv_output

    try:
        from variables_pip import census_year
    except ImportError:
        census_year = "2021"

    try:
        from variables_pip import map_output
    except ImportError:
        map_output = "sense_check_map.html"

    geometry, properties = load_boundary(polygon_p)
    print(f"Boundary loaded: {properties.get('name', '(unnamed)')}")
    print(f"  area: {geometry.area / 1e6:.2f} km2")

    inside, outside = find_oas_in_area(geometry, year=census_year)
    print(f"  {len(inside) + len(outside)} centroids searched, "
          f"{len(inside)} inside the boundary")

    write_outputs(inside, properties, oa_json_output, oa_csv_output)
    print(f"  written: {oa_json_output}")
    print(f"  written: {oa_csv_output}")

    make_sense_check_map(geometry, inside, outside, map_output)
    print(f"  written: {map_output}  <- open this to check the match")


if __name__ == "__main__":
    main()
