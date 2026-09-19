"""
Template for variables_pip.py - copy this into the project root and edit.

    cp variables_examples/variables_pip_example.py variables_pip.py

Everything machine-specific lives here so that paths from your computer never
get committed to GitHub. variables_pip.py is listed in .gitignore.

Both scripts read from this one file:
    points_in_polygon.py  uses section 1
    data_aggregates.py    uses section 2
"""

############################################################
# 1. Settings for points_in_polygon.py  (step 1)
############################################################

# The digitised boundary of your area, as GeoJSON.
# Its projection is read from the file where declared, and guessed otherwise.
polygon_p = 'notes/B006.geojson'

# Which Census the Output Areas should come from.
# Output Area boundaries were redrawn each Census, so this matters:
# '2021', '2011' or '2001'.
census_year = '2021'

# Where to write the list of matched Output Areas.
#   - the JSON keeps the coordinates and the parish details, for reference
#   - the CSV is the lookup table that step 2 reads
oa_json_output = 'output/B006_oas.json'
oa_csv_output = 'output/B006_lookup.csv'

# Where to write the map that lets you eyeball the match.
map_output = 'output/sense_check_map.html'

# NOTE: Output Area centroids are downloaded from the ONS Open Geography
# Portal automatically, so there is no national points file to fetch by hand.
# Downloads are cached in .api_cache/ - delete that folder to force a refresh.


############################################################
# 2. Settings for data_aggregates.py  (step 2)
############################################################

# The lookup file(s) produced by step 1, one per Census year.
#
# To compare a parish against its deanery and diocese, this file needs to
# cover every parish, not just yours: run step 1 once per parish boundary and
# concatenate the CSVs (they all share the same columns). With a single
# parish in the file, the parish, deanery and diocese rows will be identical.
oa_2021_output = 'output/B006_lookup.csv'
oa_2011_output = 'output/B006_lookup_2011.csv'
oa_2001_output = 'output/B006_lookup_2001.csv'

# The area you are reporting on. These match the values in your boundary
# file's properties - 'id' and 'dean'.
my_parish = ['B006']
my_deanery = ['B']

# The Census tables to process.
#
# Each entry needs a short 'dataset' name (used in the output filename) and
# either:
#     'nomis_id'  - downloaded from Nomis automatically, or
#     'path'      - read from a CSV you have already downloaded.
#
# Optional keys:
#     'data_columns' - which columns to turn into proportions. Leave it out
#                      to use every numeric column except the total.
#     'dimension'    - force a category dimension, e.g. 'C_SEX'. Only needed
#                      when a table has several and the wrong one is picked.
#
# To find a dataset ID:
#     python3 -c "import census_api; print(census_api.search_nomis_datasets('c2021ts007*'))"

datasets21 = [
    {'nomis_id': 'NM_2028_1', 'dataset': 'sex',       'description': 'TS008 Sex'},
    {'nomis_id': 'NM_2018_1', 'dataset': 'age',       'description': 'TS007B Age by broad bands'},
    {'nomis_id': 'NM_2023_1', 'dataset': 'household', 'description': 'TS003 Household composition'},
]

datasets11 = [
    {'nomis_id': 'NM_145_1', 'dataset': 'age', 'description': 'KS102EW Age structure'},
]

datasets01 = [
    {'nomis_id': 'NM_1634_1', 'dataset': 'population', 'description': 'KS001 Usual resident population'},
]

# Where the outputs go. Note the trailing slashes - filenames are appended.
#   all_data_output    - every parish and deanery, the full tables
#   report_data_output - just your parish, its deanery and the diocese total
all_data_output = [
    {'year': '2021', 'path': 'output/2021/full/'},
    {'year': '2011', 'path': 'output/2011/full/'},
    {'year': '2001', 'path': 'output/2001/full/'},
]

report_data_output = [
    {'year': '2021', 'path': 'output/2021/report/'},
    {'year': '2011', 'path': 'output/2011/report/'},
    {'year': '2001', 'path': 'output/2001/report/'},
]
