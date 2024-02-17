# Data aggregation

This code performs aggregation and preparation of the statistical, socio-demographic data for custom-defined areas. Custom areas can be defined by listing which Output Areas (OAs) belong to them. Other data comes from Nomis (Census), and other official statistics. The code is designed to be modular and reusable for different years of data. Currently we are looking at 3 years worth of data (Census 2021, 2011, 2001). The code can be easily modified to handle other data. The data sourcing and initial preparation is manual (and the process is captured in the seperate file - please explore the notes folder.)

## Key Functions

calculate_proportions(row, data_columns): Calculates proportions within a DataFrame row for specified columns.
transform_dataset(dataset, oa_data, data_columns): Loads, merges, aggregates, and calculates proportions on input data.
extract_relevant_rows(deanery_agg, parish_agg, parish_id, deanery_id): Extracts specific parish and deanery rows, including the 'Diocese' row, maintaining order.
process_year_data(year, datasets, report_data_output, oa_output, data_columns): Coordinates processing for a given year's data, loading files, transforming, and exporting results.
Usage

## Prepare Input Data:

Ensure datasets are in CSV format and located according to paths within the code.
Adjust paths or filenames within the code if needed.
Specify the column names you want to calculate proportions for in the data_columns variable.

## How to run
run python3 data_aggregates.py

NOTE: There is a fair bit of data sourcing and preparation before this code can be used in a meaningful way.

## Output

 The analysis generates the following CSV files for each processed year:

deaneries_<dataset_name>.csv: Data aggregated at the deanery level.
parishes_<dataset_name>.csv: Data aggregated at the parish level.
<dataset_name>.csv: Report containing data for the specified parishes and deanery.

NOTE: This can be carried out for multiple datasets in one go. They all need to be prepared and placed in a designated folder beforehand.

## Dependencies

Python 3.6+
Pandas

## Notes

This code assumes datasets have a specific structure. More on this in the Variables file. The paths will need adjusting (and are not provided in Github).
There is a space to capture column names for proportion calculations. This bit is manual at the moment.