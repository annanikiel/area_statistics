"""
The Census tables this project pulls, grouped by topic.

Every table listed here was checked against Nomis and is published at Output
Area level. That check matters: ONS withholds some tables at OA level to
protect people's privacy in small areas, so a table existing does not mean it
can be used here. TS024 (Main language, detailed) is one such - TS025 and
TS029 are used instead.

To see what else is available:

    import census_api
    census_api.search_nomis_datasets('c2021ts*')

Then check a candidate is published at OA level before adding it:

    import census_tables
    census_tables.check_oa_availability('NM_2043_1')
"""

# Each entry: (Nomis ID, short name used in filenames, title for display)
TABLES_2021 = {
    "Population and households": [
        ("NM_2021_1", "residents",       "TS001 Usual residents"),
        ("NM_2020_1", "age",             "TS007A Age by five-year bands"),
        ("NM_2028_1", "sex",             "TS008 Sex"),
        ("NM_2023_1", "household_type",  "TS003 Household composition"),
        ("NM_2037_1", "household_size",  "TS017 Household size"),
    ],
    "Religion, ethnicity and origin": [
        ("NM_2049_1", "religion",        "TS030 Religion"),
        ("NM_2041_1", "ethnicity",       "TS021 Ethnic group"),
        ("NM_2024_1", "country_of_birth","TS004 Country of birth"),
        ("NM_2044_1", "language",        "TS025 Household language"),
        ("NM_2048_1", "english",         "TS029 Proficiency in English"),
        ("NM_2025_1", "passports",       "TS005 Passports held"),
    ],
    "Work, education and deprivation": [
        ("NM_2083_1", "economic_activity","TS066 Economic activity status"),
        ("NM_2080_1", "occupation",      "TS063 Occupation"),
        ("NM_2079_1", "social_class",    "TS062 National Statistics Socio-economic Classification"),
        ("NM_2084_1", "qualifications",  "TS067 Highest level of qualification"),
        ("NM_2031_1", "deprivation",     "TS011 Household deprivation"),
    ],
    "Housing and health": [
        ("NM_2072_1", "tenure",          "TS054 Tenure"),
        ("NM_2062_1", "accommodation",   "TS044 Accommodation type"),
        ("NM_2063_1", "cars",            "TS045 Car or van availability"),
        ("NM_2055_1", "health",          "TS037 General health"),
        ("NM_2056_1", "disability",      "TS038 Disability"),
        ("NM_2057_1", "unpaid_care",     "TS039 Provision of unpaid care"),
    ],
}


def dataset_entries(groups=None):
    """
    Turn the catalogue into the dataset list data_aggregates.py expects.

    Args:
        groups (list): Topic groups to include. None means all of them.

    Returns:
        list: [{'nomis_id', 'dataset', 'description', 'group'}, ...]
    """
    entries = []
    for group, tables in TABLES_2021.items():
        if groups and group not in groups:
            continue
        for nomis_id, name, title in tables:
            entries.append({
                "nomis_id": nomis_id,
                "dataset": name,
                "description": title,
                "group": group,
            })
    return entries


def check_oa_availability(nomis_id, oa_type="TYPE150"):
    """
    Check whether a Nomis dataset is published at Output Area level.

    Worth running before adding a table to the catalogue - a table that is not
    published at OA level cannot be aggregated to a bespoke area at all.

    Returns:
        bool
    """
    import requests
    import census_api

    url = f"{census_api.NOMIS_BASE}/{nomis_id}/geography/TypeList.def.sdmx.json"
    payload = requests.get(url, timeout=60).json()
    codes = payload["structure"]["codelists"]["codelist"][0]["code"]
    return oa_type in {code["value"] for code in codes}


if __name__ == "__main__":
    # Print the catalogue, and confirm every table really is available at OA
    # level. Run this if you add a table.
    for group, tables in TABLES_2021.items():
        print(f"\n{group}")
        for nomis_id, name, title in tables:
            available = check_oa_availability(nomis_id)
            print(f"  {'OK ' if available else 'NOT AT OA LEVEL'} "
                  f"{name:18} {nomis_id:12} {title}")
