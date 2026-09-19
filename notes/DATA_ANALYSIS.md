# Data aggregation

This code aggregates socio-demographic data for custom-defined areas. An area
is defined by the list of Output Areas (OAs) belonging to it, which
`points_in_polygon.py` produces. The data comes from Nomis (Census) and is
downloaded automatically.

The code is modular and reusable across years. It currently covers Census 2021,
2011 and 2001, and other tables can be added by dropping their dataset ID into
the variables file.

## Key functions

| Function | What it does |
|---|---|
| `calculate_proportions(row, data_columns)` | Turns counts into proportions of the row's `Total`. |
| `load_dataset(item, oa_codes)` | Reads one Census table, from Nomis or a local CSV. |
| `transform_dataset(dataset, oa_data, data_columns)` | Merges, aggregates to parish and deanery, adds proportions. |
| `extract_relevant_rows(...)` | Pulls out the parish, deanery and diocese rows for a report. |
| `process_year_data(...)` | Runs all of the above over one year's datasets. |

## Input

The lookup CSV from step 1 — one row per OA, carrying the parish and deanery it
belongs to:

| OA | ParishID | Name | Location | Deanery |
|----|----------|------|----------|---------|
| E00172934 | B006 | St James and All Souls | Salford | B |

To compare a parish against its deanery and diocese, this file needs to cover
every parish: run step 1 once per boundary and concatenate the results.

Census tables themselves are declared in `variables_pip.py`, each as either a
`nomis_id` (downloaded) or a `path` (a CSV you already have).

## How to run

```bash
python3 data_aggregates.py
```

## Output

Per dataset, per year:

* `deaneries_<name>.csv` — every deanery, plus the diocese total row
* `parishes_<name>.csv` — every parish
* `<name>.csv` — the report: your parish, its deanery, the diocese

Several datasets are processed in one go; list them all in `datasets21`.

## Things to know

**Proportions.** Calculated against the `Total` column, which the API client
identifies and renames for you. Where an area's total is zero the proportion is
left empty rather than reported as infinity. By default every numeric column is
proportioned; set `data_columns` on a dataset entry to narrow that.

**Unmatched Output Areas.** If an OA in the lookup has no matching Census row it
would sum as zero and quietly understate the area, so the script warns instead.
Usually it means the lookup was built for a different Census year than the data.

**Derived statistics.** Tables that mix counts with figures like `Mean Age` or
population density have those columns dropped, because summing them across OAs
gives a meaningless result. The script prints which ones went.

**Mixed tables.** Some tables carry columns that are counts but not parts of the
total — 2001's KS001 includes `Area (hectares)` alongside population. The
categories will not sum to the total there, which is correct. Use
`data_columns` to proportion only what makes sense.

## Dependencies

Python 3.8+, pandas, requests. See `requirements.txt`.

**Totals differ slightly between tables.** TS008 (Sex) gives 23,254 usual
residents for a parish where TS007B (Age) gives 23,269. That is expected, not
an error: ONS applies statistical disclosure control to Census 2021, swapping
records between similar households so individuals cannot be identified. Each
table is protected independently, so small-area totals can differ by a few
people. Do not try to reconcile them — treat the total from each table as that
table's own base.
