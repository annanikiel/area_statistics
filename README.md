# Area statistics

Generate socio-economic statistics for bespoke areas — a parish, a catchment,
any area you can draw a boundary around — from ONS Census data.

Official statistics are published for areas ONS defines, which rarely line up
with the area you actually care about. This project bridges that gap: it finds
the Output Areas (OAs) that make up your area, then aggregates Census data over
them. OAs cover up to about 100 households each, so they approximate a
user-defined boundary closely.

The scripts are written to be readable with basic Python knowledge, and
commented throughout.

## What you need

* Python 3.8 or newer
* A digitised boundary for your area, as GeoJSON

That's it. Output Area centroids and Census data are downloaded automatically
(see [Where the data comes from](#where-the-data-comes-from)).

## Getting started

```bash
pip install -r requirements.txt
cp variables_examples/variables_pip_example.py variables_pip.py
```

Open `variables_pip.py` and point `polygon_p` at your boundary file. Then:

```bash
python3 points_in_polygon.py     # step 1: which OAs make up your area
python3 data_aggregates.py       # step 2: the statistics
```

Step 1 prints how many OAs it matched and writes a map — open it and check the
shape looks right before going on.

## Step 1: Geography

`points_in_polygon.py` works out which Output Areas belong to your area.

1. Reads your boundary and converts it to EPSG:27700.
2. Takes its bounding box and widens it by 300 m.
3. Downloads the OA centroids in that box from the ONS Open Geography Portal.
4. Tests each one against the boundary itself.
5. Writes the matched list, plus a map to check it by eye.

The two-stage test — cheap bounding box first, then the real geometry — keeps
it fast. Only the centroids near your boundary are downloaded, not the
190,000-odd in the national file.

**Output.** Two files. The JSON keeps coordinates and parish details for
reference. The CSV is the lookup table step 2 reads:

| OA | ParishID | Name | Location | Deanery |
|----|----------|------|----------|---------|
| E00172934 | B006 | St James and All Souls | Salford | B |

Those columns come from your boundary file's own `properties`, so the lookup
builds itself. The mapping is `PROPERTY_MAP` at the top of the script — adjust
it if your files name things differently.

### A word about projections

Points and polygon must share a projection for the matching to work. This
project uses **EPSG:27700** — the Ordnance Survey and ONS projection. It
measures in metres, which makes the buffer easy to reason about, and it is what
ONS publishes centroids in, so no conversion is needed on the points side.

Your boundary's projection is read from the file's `crs` member where there is
one, guessed from the size of the coordinates otherwise, and assumed to be
EPSG:4326 as a last resort (which is what the GeoJSON standard says). To
override it, pass `source_crs` to `load_boundary`.

EPSG:27700 also looks best in print, where maps are UK-focused. For interactive
web maps EPSG:3857 is the usual choice — the sense-check map converts to
EPSG:4326 for display, since that is what Folium expects.

### Covering more than one area

Run step 1 once per boundary and concatenate the CSVs — they all share the same
columns. You need this to compare a parish against its deanery or diocese: with
a single parish in the lookup, the parish, deanery and diocese rows are all the
same number.

## Step 2: Data

`data_aggregates.py` takes the lookup and, for each Census table, sums the
counts to parish level, deanery level and a grand total, then calculates
proportions so areas of different sizes can be compared.

See [notes/DATA_ANALYSIS.md](notes/DATA_ANALYSIS.md) for the detail.

**Output**, per dataset:

* `deaneries_<name>.csv` — every deanery, plus the diocese total
* `parishes_<name>.csv` — every parish
* `<name>.csv` — the report: your parish, its deanery, the diocese

## Where the data comes from

Both sources are open and need no API key.

| | Source | Notes |
|---|---|---|
| OA centroids | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/) | Population-weighted, EPSG:27700, 2021 / 2011 / 2001 |
| Census counts | [Nomis](https://www.nomisweb.co.uk/) | OA level, 2021 / 2011 / 2001 |

Downloads are cached in `.api_cache/`, so only the first run touches the
network. Delete that folder to refresh.

To find a Census table's dataset ID:

```python
import census_api
census_api.search_nomis_datasets('c2021ts007*')
# [{'id': 'NM_2027_1', 'mnemonic': 'c2021ts007', 'name': 'TS007 - Age by single year'}, ...]
```

Then add it to `datasets21` in `variables_pip.py`.

### Output Area boundaries change

OAs were redrawn for each Census, so 2021 OA codes do not match 2011 ones. Run
step 1 once per Census year (set `census_year`) and keep a separate lookup for
each. Comparing years means comparing whole-area totals, not individual OAs.

### Counts and derived statistics

Some Census tables mix plain counts with derived figures — 2011's age table
carries `Mean Age` alongside the age bands. Those cannot be summed across OAs
(a parish's mean is not the sum of its OAs' means), so they are dropped
automatically and the script says which. Pass `counts_only=False` to
`fetch_nomis_dataset` if you want them anyway.

## A word about variables

Paths and other machine-specific details live in `variables_pip.py`, which is
not committed. The template is in `variables_examples/`, and lists every
setting both scripts read.

## Tests

```bash
pytest
```

22 tests, all offline — the geometry is synthetic and the centroids are passed
in, so nothing touches the network.

## Repository layout

```
points_in_polygon.py    Step 1 — boundary to OA list
data_aggregates.py      Step 2 — OA list to statistics
census_api.py           Downloads from ONS and Nomis
tests/                  Offline test suite
notes/                  Data analysis notes, example boundary
variables_examples/     Template for variables_pip.py
```

## Resources

* Shapely (geometry): https://shapely.readthedocs.io/en/stable/
* Points-in-polygon tutorial: https://automating-gis-processes.github.io/2017/lessons/L3/point-in-polygon.html
* ONS Open Geography Portal: https://geoportal.statistics.gov.uk/
* Nomis API guide: https://www.nomisweb.co.uk/api/v01/help
