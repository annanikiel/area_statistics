"""
Download the reference data this project needs, straight from the official APIs.

Before this module existed, running the pipeline meant manually downloading a
national Output Area centroids file and hand-building Census extracts on the
Nomis website. Both of those are now fetched on demand:

  * OA centroids   -> ONS Open Geography Portal (ArcGIS REST)
  * Census counts  -> Nomis API

Nothing here needs an API key. Both services are open.

*** Two things worth knowing ***

1. Everything is cached on disk (see CACHE_DIR). The first run hits the network;
   later runs read the cache. Delete the cache folder to force a refresh.

2. OA centroids come back already in EPSG:27700 - the projection this project
   uses throughout - so no conversion is needed on the points side.
"""

import csv
import hashlib
import io
import json
import os
import time

import requests


############################################################
# 1. Configuration
############################################################

# Where downloaded data is cached. Override by setting the environment
# variable AREA_STATS_CACHE, or by passing cache_dir= to the functions below.
CACHE_DIR = os.environ.get(
    "AREA_STATS_CACHE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".api_cache"),
)

# ONS Open Geography Portal - population weighted centroids for Output Areas.
# Each entry is (service name, the field holding the OA code).
# These are the layers ONS publishes for each Census; they are all EPSG:27700.
CENTROID_SERVICES = {
    "2021": ("OA_December_2021_EW_PWC_V4", "OA21CD"),
    "2011": ("Output_Areas_Dec_2011_PWC_2022", "OA11CD"),
    "2001": ("Output_Areas_2001_EW_PWC", "OA01CD"),
}

ONS_BASE = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
    "/{service}/FeatureServer/0/query"
)

NOMIS_BASE = "https://www.nomisweb.co.uk/api/v01/dataset"

# Nomis geography type codes for Output Areas, per Census year.
# (Nomis calls these "TYPE" codes; they differ between Censuses because the
# Output Area boundaries were redrawn each time.)
NOMIS_OA_TYPE = {"2021": "TYPE150", "2011": "TYPE299", "2001": "TYPE310"}

# How many OA codes to request from Nomis in a single call. Nomis accepts a
# comma-separated list in the URL, so this keeps the URL to a sane length.
NOMIS_BATCH_SIZE = 100

# Some Census tables mix plain counts with derived statistics - 2011's age
# table, for example, carries "Mean Age" and "Median Age" alongside the age
# bands. Those must NOT be summed across Output Areas (the mean of a parish is
# not the sum of its OAs' means), so they are dropped by default.
DERIVED_COLUMN_HINTS = (
    "mean", "median", "average", "density", "ratio", "rate",
    "per cent", "percentage", "index", "per hectare",
)


def is_count_column(name):
    """True if a column looks like a count that can safely be summed."""
    lowered = str(name).lower()
    return not any(hint in lowered for hint in DERIVED_COLUMN_HINTS)


# Columns Nomis always returns that are not category dimensions.
_NOMIS_NON_DIMENSIONS = {
    "DATE", "GEOGRAPHY", "MEASURES", "OBS_STATUS", "OBS_CONF", "RECORD",
}


############################################################
# 2. Small helpers
############################################################

def _cache_path(kind, key, suffix, cache_dir=None):
    """Build a stable cache filename from a request key."""
    cache_dir = cache_dir or CACHE_DIR
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    folder = os.path.join(cache_dir, kind)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{digest}{suffix}")


def _get(url, params, retries=4, timeout=120):
    """
    GET a URL, retrying on transient network errors with a growing wait.

    Public APIs occasionally time out or rate-limit; this keeps a long run from
    falling over on a single blip.
    """
    wait = 2
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(wait)
                wait *= 2
    raise RuntimeError(f"Request failed after {retries} attempts: {url}\n{last_error}")


############################################################
# 3. OA centroids, from ONS Open Geography Portal
############################################################

def fetch_oa_centroids(bbox, year="2021", cache_dir=None, use_cache=True):
    """
    Fetch Output Area population-weighted centroids inside a bounding box.

    Only the centroids in the box are downloaded, so this stays fast even
    though the national file has ~190,000 points in it.

    Args:
        bbox (tuple): (minx, miny, maxx, maxy) in EPSG:27700 metres.
        year (str): Census year - '2021', '2011' or '2001'.
        cache_dir (str): Override the cache location.
        use_cache (bool): Set False to always re-download.

    Returns:
        list: [[oa_code, x, y], ...] with x/y as floats in EPSG:27700.
              The same shape the rest of this project expects.
    """
    if year not in CENTROID_SERVICES:
        raise ValueError(
            f"No centroid layer known for year {year!r}. "
            f"Options: {sorted(CENTROID_SERVICES)}"
        )

    service, code_field = CENTROID_SERVICES[year]
    key = f"{service}|{bbox}"
    path = _cache_path("centroids", key, ".json", cache_dir)

    if use_cache and os.path.exists(path):
        with open(path) as handle:
            return json.load(handle)

    minx, miny, maxx, maxy = bbox
    url = ONS_BASE.format(service=service)

    centroids = []
    offset = 0
    while True:
        params = {
            "geometry": f"{minx},{miny},{maxx},{maxy}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "27700",
            "outSR": "27700",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": code_field,
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json",
        }
        payload = _get(url, params).json()

        if "error" in payload:
            raise RuntimeError(f"ONS API error: {payload['error']}")

        features = payload.get("features", [])
        for feature in features:
            geometry = feature.get("geometry") or {}
            if "x" not in geometry or "y" not in geometry:
                continue  # skip any feature without a usable point
            centroids.append([
                feature["attributes"][code_field],
                float(geometry["x"]),
                float(geometry["y"]),
            ])

        # The service caps each response; keep asking until it stops saying
        # there is more to come.
        if not payload.get("exceededTransferLimit") or not features:
            break
        offset += len(features)

    with open(path, "w") as handle:
        json.dump(centroids, handle)

    return centroids


############################################################
# 4. Census counts, from Nomis
############################################################

def search_nomis_datasets(search):
    """
    Look up Nomis dataset IDs by search term.

    Useful when you know the table you want but not its ID, e.g.
        search_nomis_datasets('c2021ts007*')
        search_nomis_datasets('ks102*')

    Returns:
        list: [{'id', 'mnemonic', 'name'}, ...]
    """
    payload = _get(f"{NOMIS_BASE}/def.sdmx.json", {"search": search}).json()
    families = payload["structure"]["keyfamilies"]
    if not families:
        return []

    results = []
    for family in families["keyfamily"]:
        notes = {
            note["annotationtitle"]: note.get("annotationtext")
            for note in family["annotations"]["annotation"]
        }
        results.append({
            "id": family["id"],
            "mnemonic": notes.get("Mnemonic", ""),
            "name": family["name"]["value"],
        })
    return results


def _nomis_dimensions(header):
    """
    Work out which Nomis columns are category dimensions.

    Nomis returns data in "long" format, one row per area per category. Every
    category dimension appears as a pair of columns, e.g. C_SEX and C_SEX_NAME.
    This spots those pairs and ignores the housekeeping columns.
    """
    columns = set(header)
    dimensions = []
    for column in header:
        if column.endswith("_NAME"):
            continue
        if column in _NOMIS_NON_DIMENSIONS:
            continue
        if f"{column}_NAME" in columns:
            dimensions.append(column)
    return dimensions


def fetch_nomis_dataset(dataset_id, oa_codes, dimension=None, cache_dir=None,
                        use_cache=True, counts_only=True):
    """
    Fetch an OA-level Census table from Nomis and reshape it into a wide table.

    Nomis serves "long" data - one row per area per category. The rest of this
    project wants one row per OA with a column per category, so this pivots it.

    Where a table has more than one category dimension (2011 tables often carry
    a Rural/Urban split alongside the real categories), the dimension with the
    most categories is used and the others are held at their total.

    Args:
        dataset_id (str): Nomis dataset ID, e.g. 'NM_2028_1'. Find one with
            search_nomis_datasets().
        oa_codes (list): OA codes to fetch, e.g. ['E00028974', ...].
        dimension (str): Force a particular category dimension, e.g. 'C_SEX'.
            Leave as None to pick automatically.
        counts_only (bool): Drop derived statistics such as 'Mean Age' that
            cannot meaningfully be summed. Set False to keep them.
        cache_dir (str): Override the cache location.
        use_cache (bool): Set False to always re-download.

    Returns:
        pandas.DataFrame: indexed by OA code, one column per category. Where a
        total category can be identified it is named 'Total'.
    """
    import pandas as pd  # imported here so the geo scripts do not need pandas

    oa_codes = list(dict.fromkeys(oa_codes))  # de-duplicate, keep order
    if not oa_codes:
        raise ValueError("No OA codes given - nothing to fetch.")

    key = f"{dataset_id}|{dimension}|{','.join(sorted(oa_codes))}"
    path = _cache_path("nomis", key, ".csv", cache_dir)

    if use_cache and os.path.exists(path):
        rows = list(csv.reader(open(path)))
    else:
        rows = []
        header = None
        # Request in batches so the URL never gets too long.
        for start in range(0, len(oa_codes), NOMIS_BATCH_SIZE):
            batch = oa_codes[start:start + NOMIS_BATCH_SIZE]
            response = _get(
                f"{NOMIS_BASE}/{dataset_id}.data.csv",
                {"geography": ",".join(batch), "measures": "20100"},
            )
            batch_rows = list(csv.reader(io.StringIO(response.text)))
            if not batch_rows:
                continue
            if header is None:
                header = batch_rows[0]
                rows.append(header)
            rows.extend(batch_rows[1:])

        if header is None:
            raise RuntimeError(f"Nomis returned no data for {dataset_id}.")

        with open(path, "w", newline="") as handle:
            csv.writer(handle).writerows(rows)

    frame = pd.DataFrame(rows[1:], columns=rows[0])
    if frame.empty:
        raise RuntimeError(f"Nomis returned no rows for {dataset_id}.")

    frame["OBS_VALUE"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")

    # Pick the category dimension to spread across columns.
    dimensions = _nomis_dimensions(list(frame.columns))
    if not dimensions:
        raise RuntimeError(f"Could not find a category dimension in {dataset_id}.")

    if dimension is None:
        dimension = max(dimensions, key=lambda d: frame[d].nunique())

    # Hold any other dimension at its total (Nomis uses code '0' for totals).
    for other in dimensions:
        if other == dimension:
            continue
        totals = frame[frame[other].astype(str) == "0"]
        if not totals.empty:
            frame = totals

    wide = frame.pivot_table(
        index="GEOGRAPHY_CODE",
        columns=f"{dimension}_NAME",
        values="OBS_VALUE",
        aggfunc="sum",
    )
    wide.index.name = "OA"
    wide.columns.name = None

    # Identify the total column so downstream proportion maths has one to use.
    total_names = frame[frame[dimension].astype(str) == "0"][f"{dimension}_NAME"].unique()
    if len(total_names) == 0:
        # 2011-style tables number their cells; the first cell is the total.
        first = frame.sort_values(dimension)[f"{dimension}_NAME"].iloc[0]
        total_names = [first]

    if total_names[0] in wide.columns:
        wide = wide.rename(columns={total_names[0]: "Total"})

    # Drop derived statistics so they are never summed by mistake.
    dropped = []
    if counts_only:
        dropped = [c for c in wide.columns if not is_count_column(c)]
        if dropped:
            wide = wide.drop(columns=dropped)

    # Record what happened so callers can report it (pandas keeps .attrs).
    wide.attrs["dataset_id"] = dataset_id
    wide.attrs["dimension"] = dimension
    wide.attrs["dropped_columns"] = dropped

    return wide
