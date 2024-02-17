# Libraries
import pandas as pd

from variables_pip import oa_2021_output, oa_2011_output, oa_2001_output
from variables_pip import datasets21, datasets11, datasets01
from variables_pip import all_data_output, report_data_output

# *** Why use functions? ***
# Functions help us break down our code into smaller, reusable pieces. This makes our code:
#   * Easier to read: Each function has a clear name and purpose.
#   * Easier to fix:  If there's a problem, we can focus on the specific function causing it.
#   * More organized: We can avoid repeating the same code over and over. 

# *** Functions in this code ***

# 1. calculate_proportions:
#    * Takes a set of data and figures out the proportions (like percentages) of specific parts.

# 2. transform_dataset:
#    * Takes a bunch of data and prepares it for analysis:
#       - Combines related information
#       - Groups data into categories
#       - Calculates proportions (using the function 1 above)

# 3. extract_relevant_rows 
#    * Pulls out specific pieces of data that we're interested in 

# 4. process_years_data
#    * Puts all of above into action to process all datasets for a given year

def calculate_proportions(row, data_columns):
    """
    Calculates proportions for specified columns within a DataFrame row.

    Args:
        row (pd.Series): A single row from a DataFrame.
        data_columns (list): A list of column names for which to calculate proportions.

    Returns:
        pd.Series: The modified row with new columns containing calculated proportions.
    """
        
    total = row['Total']
    for col in data_columns:  # Replace 'data_columns' with a list of your actual column names
        if col != 'Total':  
            row[f'{col}_prop'] = row[col] / total
    return row  


def transform_dataset(dataset, oa_data, data_columns):
    """
    Transforms a dataset by merging with OA data, aggregating at deanery and parish 
    levels, and calculating proportions based on specified columns.

    Args:
        dataset (pd.DataFrame): The input dataset to transform.
        oa_data (pd.DataFrame): The OA (Output Area) data for merging.
        data_columns (list): A list of column names used for proportion calculations.

    Returns:
        tuple: A tuple containing two DataFrames: 
               * deanery_agg: Data aggregated at the deanery level with proportions.
               * parish_agg: Data aggregated at the parish level with proportions.
    """
        
    # Merge with OA data
    merged_df = pd.merge(left=oa_data, right=dataset, left_on='OA', right_on='oa21', how='left')
    merged_df = merged_df.drop(columns=['oa21'])

    # Aggregate at deanery level
    deanery_agg = merged_df.drop(columns=['OA', 'ParishID', 'Name', 'Location', 'Status'])
    deanery_agg = deanery_agg.groupby('Deanery').sum()
    deanery_agg.loc['Diocese'] = deanery_agg.sum(axis=0)

    # Aggregate at parish level
    parish_agg = merged_df.drop(columns=['OA', 'Name', 'Location', 'Status', 'Deanery'])
    parish_agg = parish_agg.groupby('ParishID').sum()

    # Calculate proportions
    deanery_agg = deanery_agg.apply(calculate_proportions, axis=1, args=(data_columns,))
    parish_agg = parish_agg.apply(calculate_proportions, axis=1, args=(data_columns,))  

    del merged_df
    return deanery_agg, parish_agg

def extract_relevant_rows(deanery_agg, parish_agg, parish_id, deanery_id, parish_name):
    """
    Extracts rows of interest from deanery and parish datasets for single or multiple
    parishes, ensuring the Diocese row is included and maintaining order.

    Args:
        deanery_agg (pd.DataFrame): The deanery aggregation DataFrame.
        parish_agg (pd.DataFrame): The parish aggregation DataFrame.
        parish_ids (list):  The ParishID to filter for.
        deanery_id (list): The DeaneryID to filter for.
        parish_name (str): Parish name to use in resulting data frame, instead of parish code

    Returns:
        pd.DataFrame: A DataFrame containing the filtered and ordered rows.
    """

    # Filter parish rows
    parish_rows = parish_agg.loc[parish_id]

    # Filter deanery and diocese rows
    deanery_row = deanery_agg.loc[deanery_id]
    diocese_row = deanery_agg.loc[['Diocese']]

    # Combine DataFrames (parishes first, then deanery and diocese)
    result = pd.concat([parish_rows, deanery_row, diocese_row], axis=0)

    # Rename parish rows and deanery rows
    result.rename(index={parish_id[0]: parish_name}, inplace=True)
    result.rename(index={deanery_id[0]: "Deanery"}, inplace=True)

    return result


def process_year_data(year, datasets, all_data_output, report_data_output, oas, parish, deanery):
    """
    Processes the datasets for a given year.

    Args:
        year (str): The year to process (e.g., '2021').
        datasets (list): List of dataset dictionaries (each having 'path', 'dataset', 'description').
        report_data_output (list): List of report dictionaries (each having 'path' and 'year').
        oa_output (str): Path to the OA output CSV file.
        data_columns (list): List of columns to use for proportion calculations.
    """

    # Load OA data
    OA = pd.read_csv(oas)  

    # Extract paths for the specified year
    path_full = [element['path'] for element in all_data_output if element['year'] == year][0] 
    path_report = [element['path'] for element in report_data_output if element['year'] == year][0] 

    # Process each dataset
    for item in datasets:
        deanery_data, parish_data = transform_dataset(pd.read_csv(item['path']), OA, item['data_columns'])
        my_parish_data = extract_relevant_rows(deanery_data, parish_data, parish, deanery, 'Parish') # 'Parish' string is a name replacement for Parish ID in the resulting data frame

        # Set filenames with year 
        path_full_dean = path_full + 'deaneries_'+item['dataset']+'.csv'
        path_full_parish = path_full + 'parishes_'+item['dataset']+'.csv'
        path_report = path_report + item['dataset']+'.csv'

        # Export to csvs
        deanery_data.to_csv(path_full_dean)
        parish_data.to_csv(path_full_parish)
        my_parish_data.to_csv(path_report)

        print(item['description'] + "....done")

##########################################################################################################################

# Generate the datasets
process_year_data('2021', datasets21, all_data_output, report_data_output, oa_2021_output, ['B006'], ['B'])