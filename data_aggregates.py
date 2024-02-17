# Libraries
import pandas as pd


# 2021 data
# In this section we are reading in the file paths to the file with matched parish to OA, and other data, mainly from census 2021, related to 2021 analysis.
from variables_pip import oa_2021_output, asg21


# Data frames
OA = pd.read_csv(oa_2021_output)
asg21 = pd.read_csv(asg21)


# Merge
# These are left joins on the data frame with OA to parish matches and the datasets. There will be a bit of cleaning and calculation later on.
asg21_d = pd.merge(left=OA, right=asg21, left_on='OA', right_on='oa21', how='left')
asg21_d = asg21_d.drop(columns=['oa21'])
del asg21



#print(asg21_d.head())

# Aggregated
# https://datagy.io/pandas-groupby/

sums = {}
print(asg21_d.dtypes)
# Split dataset by deanery
for Deanery in asg21_d['Deanery'].unique():
    tempdf = [asg21_d['Deanery'] == Deanery]
    
    print(tempdf)
    
    sum = tempdf['Total'].sum()
    sums[Deanery] = [sum]

    sum = tempdf['AB'].sum()
    sums[Deanery] = [sum]

asg21_dean = pd.DataFrame.from_dict(sums)

print(asg21_dean)














