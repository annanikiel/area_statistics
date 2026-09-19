"""
Build everything: boundaries in, full set of statistics out.

One command takes a boundary file containing every parish and produces, for
each of the Census tables in census_tables.py, figures at parish, deanery and
diocese level - plus the data the dashboard reads.

    python3 build_all.py                          # everything
    python3 build_all.py --groups "Housing and health"
    python3 build_all.py --boundaries notes/diocese.geojson

What it writes:

    results/2021/lookup.csv          which OAs make up each parish
    results/2021/parishes/*.csv      every parish, one file per table
    results/2021/deaneries/*.csv     every deanery plus the diocese total
    results/2021/summary.csv         headline figures per parish
    docs/data/*.json                 the dashboard's data
    docs/sense_check_map.html        the map

Run time is mostly downloading. The first run fetches everything; later runs
read the cache in .api_cache/, so they take seconds.
"""

import argparse
import json
import os
import shutil
import warnings
from datetime import date

import pandas as pd

import census_tables
import data_aggregates as agg
import points_in_polygon as pip


DEFAULT_BOUNDARIES = "notes/B006.geojson"
DEFAULT_RESULTS = "results"
DEFAULT_DOCS = "docs"


############################################################
# Step 1: boundaries -> lookup
############################################################

def build_lookup(boundaries_path, year, results_dir, docs_dir):
    """Match Output Areas to every area in the boundary file."""
    print(f"Reading boundaries from {boundaries_path}")
    areas = pip.load_boundaries(boundaries_path)
    print(f"  {len(areas)} area(s) found")

    matches, report = pip.match_all_areas(areas, year=year)
    print(f"  {report['centroids_searched']} centroids searched, "
          f"{report['matched']} matched to an area")

    # These two are worth knowing about rather than discovering later.
    if report["empty_areas"]:
        warnings.warn(
            f"{len(report['empty_areas'])} area(s) matched no Output Areas at "
            f"all: {report['empty_areas'][:5]}. They may be too small to "
            "contain a centroid, or in a different projection.", stacklevel=2)
    if report["overlaps"]:
        warnings.warn(
            f"{len(report['overlaps'])} Output Area(s) fall inside more than "
            "one boundary and will be counted twice in the deanery and "
            f"diocese totals: {list(report['overlaps'])[:5]}", stacklevel=2)

    lookup_path = os.path.join(results_dir, year, "lookup.csv")
    pip.write_combined_lookup(matches, lookup_path)
    print(f"  written: {lookup_path}")

    # The map covers every area, so the whole set can be checked at once.
    combined, _ = pip.load_boundary(boundaries_path)
    inside = [[m["OA"], m["x"], m["y"]] for m in matches]
    matched_codes = {m["OA"] for m in matches}
    all_centroids = pip.census_api.fetch_oa_centroids(
        pip.buffered_bounds(combined), year=year)
    outside = [c for c in all_centroids if c[0] not in matched_codes]

    os.makedirs(docs_dir, exist_ok=True)
    map_path = os.path.join(docs_dir, "sense_check_map.html")
    pip.make_sense_check_map(combined, inside, outside, map_path)
    print(f"  written: {map_path}")

    return lookup_path, report


############################################################
# Step 2: lookup -> statistics
############################################################

def build_tables(lookup_path, year, groups, results_dir):
    """Run every catalogued table through the aggregation."""
    oa_data = pd.read_csv(lookup_path)
    oa_codes = oa_data[agg.OA_COLUMN].dropna().unique().tolist()

    entries = census_tables.dataset_entries(groups)
    print(f"\nProcessing {len(entries)} table(s) over {len(oa_codes)} "
          "Output Area(s)")

    parishes_dir = os.path.join(results_dir, year, "parishes")
    deaneries_dir = os.path.join(results_dir, year, "deaneries")
    for folder in (parishes_dir, deaneries_dir):
        os.makedirs(folder, exist_ok=True)

    built = []
    for number, item in enumerate(entries, start=1):
        label = f"[{number}/{len(entries)}] {item['description']}"
        try:
            dataset = agg.load_dataset(item, oa_codes)
            with warnings.catch_warnings():
                # One warning per table about unmatched OAs is enough; the
                # lookup step already reported the overall picture.
                warnings.simplefilter("once")
                deanery, parish = agg.transform_dataset(dataset, oa_data)
        except Exception as error:
            print(f"  {label}: FAILED - {type(error).__name__}: {error}")
            continue

        parish.to_csv(os.path.join(parishes_dir, f"{item['dataset']}.csv"))
        deanery.to_csv(os.path.join(deaneries_dir, f"{item['dataset']}.csv"))

        built.append({**item, "columns": [c for c in parish.columns
                                          if not str(c).endswith("_prop")]})
        print(f"  {label}: {parish.shape[0]} parishes x "
              f"{len(built[-1]['columns'])} columns")

    return built


############################################################
# Step 3: a headline summary
############################################################

def build_summary(results_dir, year, built):
    """One row per parish with the figures worth seeing first."""
    parishes_dir = os.path.join(results_dir, year, "parishes")

    def read(name):
        path = os.path.join(parishes_dir, f"{name}.csv")
        return pd.read_csv(path, index_col=0) if os.path.exists(path) else None

    names = {b["dataset"] for b in built}
    summary = pd.DataFrame()

    if "sex" in names:
        sex = read("sex")
        summary["Residents"] = sex["Total"]
        if "Female" in sex:
            summary["Female %"] = (sex["Female"] / sex["Total"] * 100).round(1)

    if "religion" in names:
        religion = read("religion")
        catholic = [c for c in religion.columns if "catholic" in str(c).lower()]
        christian = [c for c in religion.columns if str(c).strip() == "Christian"]
        column = catholic[0] if catholic else (christian[0] if christian else None)
        if column:
            summary[f"{column} %"] = (
                religion[column] / religion["Total"] * 100).round(1)

    if "deprivation" in names:
        dep = read("deprivation")
        not_deprived = [c for c in dep.columns
                        if "not deprived" in str(c).lower()]
        if not_deprived:
            summary["Deprived in 1+ dimension %"] = (
                (1 - dep[not_deprived[0]] / dep["Total"]) * 100).round(1)

    if "health" in names:
        health = read("health")
        bad = [c for c in health.columns
               if str(c).lower().startswith(("bad", "very bad"))]
        if bad:
            summary["Bad or very bad health %"] = (
                health[bad].sum(axis=1) / health["Total"] * 100).round(1)

    if summary.empty:
        return None

    path = os.path.join(results_dir, year, "summary.csv")
    summary.to_csv(path)
    print(f"\n  written: {path}")
    return summary


############################################################
# Step 4: data for the dashboard
############################################################

def build_dashboard_data(results_dir, year, built, report, docs_dir,
                         lookup_path):
    """
    Write the JSON the dashboard page reads.

    Counts and proportions for every table at all three levels, kept small
    enough to load in a browser.
    """
    data_dir = os.path.join(docs_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    lookup = pd.read_csv(lookup_path)
    parish_names = {}
    if "ParishID" in lookup.columns and "Name" in lookup.columns:
        parish_names = (lookup.drop_duplicates("ParishID")
                        .set_index("ParishID")["Name"].to_dict())

    catalogue = []
    for item in built:
        parish = pd.read_csv(
            os.path.join(results_dir, year, "parishes", f"{item['dataset']}.csv"),
            index_col=0)
        deanery = pd.read_csv(
            os.path.join(results_dir, year, "deaneries", f"{item['dataset']}.csv"),
            index_col=0)

        counts = [c for c in parish.columns if not str(c).endswith("_prop")]
        categories = [c for c in counts if c != "Total"]

        def rows(frame):
            out = {}
            for label, row in frame.iterrows():
                total = row.get("Total")
                out[str(label)] = {
                    "total": None if pd.isna(total) else float(total),
                    "values": [None if pd.isna(row[c]) else float(row[c])
                               for c in categories],
                }
            return out

        payload = {
            "dataset": item["dataset"],
            "title": item["description"],
            "group": item["group"],
            "categories": categories,
            "parishes": rows(parish),
            "deaneries": rows(deanery),
        }
        with open(os.path.join(data_dir, f"{item['dataset']}.json"), "w") as handle:
            json.dump(payload, handle)

        catalogue.append({"dataset": item["dataset"],
                          "title": item["description"],
                          "group": item["group"],
                          "categories": len(categories)})

    index = {
        "year": year,
        "built": date.today().isoformat(),
        "parish_names": parish_names,
        "parishes": sorted(parish_names) or sorted(
            {str(k) for k in report["per_area"]}),
        "output_areas": report["matched"],
        "areas": report["areas"],
        "overlaps": len(report["overlaps"]),
        "empty_areas": report["empty_areas"],
        "tables": catalogue,
        "groups": list(census_tables.TABLES_2021),
    }
    with open(os.path.join(data_dir, "index.json"), "w") as handle:
        json.dump(index, handle, indent=1)

    print(f"  written: {data_dir}/ ({len(catalogue)} tables + index)")
    return index


############################################################
# Putting it together
############################################################

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boundaries", default=DEFAULT_BOUNDARIES,
                        help="GeoJSON with one feature per parish")
    parser.add_argument("--year", default="2021", choices=["2021", "2011", "2001"])
    parser.add_argument("--groups", nargs="*", default=None,
                        help="Topic groups to include (default: all)")
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--docs", default=DEFAULT_DOCS)
    parser.add_argument("--clean", action="store_true",
                        help="Delete previous results first")
    args = parser.parse_args()

    if args.clean and os.path.exists(args.results):
        shutil.rmtree(args.results)

    lookup_path, report = build_lookup(args.boundaries, args.year,
                                       args.results, args.docs)
    built = build_tables(lookup_path, args.year, args.groups, args.results)

    if not built:
        print("\nNo tables were built - stopping.")
        return 1

    build_summary(args.results, args.year, built)
    build_dashboard_data(args.results, args.year, built, report, args.docs,
                         lookup_path)

    print(f"\nDone. {len(built)} table(s) built for {report['areas']} area(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
