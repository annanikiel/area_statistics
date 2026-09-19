"""
Step 2: turn Output Area Census data into statistics for your areas.

This takes the OA lookup produced by step 1 (points_in_polygon.py) and, for
each Census table, adds the numbers up to parish level, deanery level and
diocese total, then works out proportions so areas of different sizes can be
compared.

*** Why use functions? ***

Functions help us break down our code into smaller, reusable pieces. This makes
our code:
  * Easier to read: Each function has a clear name and purpose.
  * Easier to fix:  If there's a problem, we can focus on the specific function
                    causing it.
  * More organized: We can avoid repeating the same code over and over.

*** Functions in this code ***

1. calculate_proportions - turns counts into proportions of the total.
2. load_dataset          - reads one Census table, from Nomis or a local CSV.
3. transform_dataset     - merges, aggregates and adds proportions.
4. extract_relevant_rows - pulls out the rows wanted for a report.
5. process_year_data     - runs all of the above over a year's datasets.

*** How to run ***

    python3 data_aggregates.py

Settings come from variables_pip.py - see variables_examples/ for a template.
"""

import warnings

import pandas as pd

import census_api


# The column holding the Output Area code, in both the lookup and the data.
OA_COLUMN = "OA"

# Grouping columns. The first is the finest level, the second the coarser one.
PARISH_COLUMN = "ParishID"
DEANERY_COLUMN = "Deanery"

# Name given to the grand-total row added to the deanery table.
TOTAL_ROW_NAME = "Diocese"


def calculate_proportions(row, data_columns=None):
    """
    Calculates proportions for specified columns within a DataFrame row.

    Args:
        row (pd.Series): A single row from a DataFrame.
        data_columns (list): Column names to calculate proportions for. Leave
            as None to use every numeric column except the total.

    Returns:
        pd.Series: The row with extra '<column>_prop' columns added.
    """
    total = row.get("Total")

    if data_columns is None:
        data_columns = [c for c in row.index
                        if c != "Total" and not str(c).endswith("_prop")]

    for col in data_columns:
        if col == "Total":
            continue
        # An area with no people in it would otherwise give a divide-by-zero,
        # which pandas reports as infinity rather than as an error. Leaving the
        # proportion empty is the honest answer.
        if not total or pd.isna(total):
            row[f"{col}_prop"] = pd.NA
        else:
            row[f"{col}_prop"] = row[col] / total

    return row


def load_dataset(item, oa_codes=None):
    """
    Load one Census table, either from Nomis or from a local CSV.

    A dataset entry is a dictionary. Give it either:
        {'nomis_id': 'NM_2028_1', ...}   - downloaded via the API, or
        {'path': 'data/sex.csv', ...}    - read from disk.

    Args:
        item (dict): The dataset entry.
        oa_codes (list): OA codes to request (Nomis only).

    Returns:
        pd.DataFrame: indexed by OA code, one column per category.
    """
    if item.get("nomis_id"):
        if not oa_codes:
            raise ValueError(
                f"{item['nomis_id']} comes from Nomis, so the OA codes are "
                "needed. Check the lookup file loaded correctly."
            )
        return census_api.fetch_nomis_dataset(
            item["nomis_id"], oa_codes, dimension=item.get("dimension")
        )

    frame = pd.read_csv(item["path"])
    # Accept whichever OA column name the file happens to use.
    for candidate in (OA_COLUMN, "oa21", "oa11", "oa01", "GEOGRAPHY_CODE"):
        if candidate in frame.columns:
            return frame.set_index(candidate).rename_axis(OA_COLUMN)

    raise ValueError(
        f"Could not find an Output Area column in {item['path']}. "
        f"Expected one of: {OA_COLUMN}, oa21, oa11, oa01, GEOGRAPHY_CODE."
    )


def transform_dataset(dataset, oa_data, data_columns=None):
    """
    Transforms a dataset by merging with OA data, aggregating at deanery and
    parish levels, and calculating proportions.

    Args:
        dataset (pd.DataFrame): Census table indexed by OA code.
        oa_data (pd.DataFrame): The OA lookup, with an OA column plus the
            parish and deanery each OA belongs to.
        data_columns (list): Columns to calculate proportions for.

    Returns:
        tuple: (deanery_agg, parish_agg) - both with proportions added.
    """
    merged = pd.merge(
        left=oa_data, right=dataset,
        left_on=OA_COLUMN, right_index=True, how="left",
    )

    # An OA in the lookup with no matching Census row would sum as zero and
    # quietly understate the area. Say so rather than let it slide.
    value_columns = dataset.columns
    unmatched = merged[value_columns].isna().all(axis=1)
    if unmatched.any():
        missing = merged.loc[unmatched, OA_COLUMN].tolist()
        warnings.warn(
            f"{len(missing)} Output Area(s) had no data and will count as "
            f"zero: {missing[:5]}{' ...' if len(missing) > 5 else ''}",
            stacklevel=2,
        )

    # Only numeric columns can be summed; this avoids having to list the
    # label columns to drop, which differ between lookup files.
    numeric = merged.select_dtypes("number").columns.tolist()

    deanery_agg = merged.groupby(DEANERY_COLUMN)[numeric].sum()
    deanery_agg.loc[TOTAL_ROW_NAME] = deanery_agg.sum(axis=0)

    parish_agg = merged.groupby(PARISH_COLUMN)[numeric].sum()

    deanery_agg = deanery_agg.apply(calculate_proportions, axis=1,
                                    args=(data_columns,))
    parish_agg = parish_agg.apply(calculate_proportions, axis=1,
                                  args=(data_columns,))

    return deanery_agg, parish_agg


def extract_relevant_rows(deanery_agg, parish_agg, parish_id, deanery_id,
                          parish_name=None):
    """
    Extracts the rows wanted for a report: the parish or parishes, their
    deanery, and the diocese total, in that order.

    Args:
        deanery_agg (pd.DataFrame): The deanery aggregation.
        parish_agg (pd.DataFrame): The parish aggregation.
        parish_id (list): ParishIDs to include.
        deanery_id (list): Deanery codes to include.
        parish_name (str or dict): A friendlier label for the parish rows. Pass
            a string to rename a single parish, or a dict to rename several.

    Returns:
        pd.DataFrame: the filtered rows.
    """
    parish_rows = parish_agg.loc[parish_id]
    deanery_rows = deanery_agg.loc[deanery_id]
    total_row = deanery_agg.loc[[TOTAL_ROW_NAME]]

    result = pd.concat([parish_rows, deanery_rows, total_row], axis=0)

    # Rename for readability. Handles one parish or several.
    if isinstance(parish_name, dict):
        renames = dict(parish_name)
    elif parish_name and len(parish_id) == 1:
        renames = {parish_id[0]: parish_name}
    else:
        renames = {}

    for code in deanery_id:
        renames[code] = f"Deanery {code}"

    return result.rename(index=renames)


def process_year_data(year, datasets, all_data_output, report_data_output,
                      oas, parish, deanery, parish_name="Parish"):
    """
    Processes every dataset for a given year.

    Args:
        year (str): The year to process, e.g. '2021'.
        datasets (list): Dataset entries - see load_dataset for their shape.
        all_data_output (list): [{'year', 'path'}] - folder for the full tables.
        report_data_output (list): [{'year', 'path'}] - folder for the report.
        oas (str): Path to the OA lookup CSV from step 1.
        parish (list): ParishIDs to report on.
        deanery (list): Deanery codes to report on.
        parish_name (str): Label to use for the parish row in the report.
    """
    oa_data = pd.read_csv(oas)
    oa_codes = oa_data[OA_COLUMN].dropna().unique().tolist()
    print(f"{year}: {len(oa_codes)} Output Areas in the lookup")

    # Find the output folders for this year.
    folder_full = [e["path"] for e in all_data_output if e["year"] == year][0]
    folder_report = [e["path"] for e in report_data_output if e["year"] == year][0]

    for item in datasets:
        dataset = load_dataset(item, oa_codes)

        if dataset.attrs.get("dropped_columns"):
            print(f"  note: dropped derived column(s) "
                  f"{dataset.attrs['dropped_columns']} - they cannot be summed")

        deanery_data, parish_data = transform_dataset(
            dataset, oa_data, item.get("data_columns")
        )
        report = extract_relevant_rows(
            deanery_data, parish_data, parish, deanery, parish_name
        )

        # Build each filename from the folder, so one dataset's name never
        # gets appended onto the next one's path.
        name = item["dataset"]
        deanery_data.to_csv(f"{folder_full}deaneries_{name}.csv")
        parish_data.to_csv(f"{folder_full}parishes_{name}.csv")
        report.to_csv(f"{folder_report}{name}.csv")

        print(f"  {item.get('description', name)} ....done")


def main():
    from variables_pip import oa_2021_output, datasets21
    from variables_pip import all_data_output, report_data_output
    from variables_pip import my_parish, my_deanery

    process_year_data("2021", datasets21, all_data_output, report_data_output,
                      oa_2021_output, my_parish, my_deanery)


if __name__ == "__main__":
    main()
