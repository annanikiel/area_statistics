# Area statistics
This project provides Python files to generate socio-economic statistics for bespoke areas like parishes, defined by digitized boundaries. The scripts are designed to be user-friendly for individuals with basic Python knowledge, with detailed instructions and code comments.This document walks you through the process of matching point location data to parish polygons, enabling extraction of comprehensive statistics like population structure, income levels, and housing characteristics.

# Steps

## Step 1: Geography data
To analyze an area not predefined by ONS, we first require its digitized boundary. Next, we identify the underlying ONS Output Areas (OAs) contained within that boundary, using a "points in polygon" script. This will return a list, which can then be used to match and aggregate OA Census data. OAs represent small units covering up to 100 households, making them ideal for approximating diverse user-defined areas.

The script in this repository was designed to work with specific types of files. Python, with the help of external libraries, can work with multitude of geographic files, however the structure may be different, so the script will require tweaking. The first step is to export POLYGON defining the area.

### A word about projections...
Geograpical data can use a wide variety of projections. In order for the matching between points and polygon to work, both need to use the same projection. This script uses EPSG:27700 - the same projection as employed by Ordnance Survey and Office for National Statistics (ONS). The script includes an example of conversion.

EPSG:27700 is also designed to look best in printed materials, where maps are UK-focused. For this reason this is used throughout. For presentation on interactive maps online, EPSG:3857 is most commonly used, although the exact detail needes to be verified in documentation for the mapping library in use.

### A word about variables...
In order to avoid commiting paths to file, and other details that are specific to the individual machine, these are stored in a seperate file, not commited to github. The examples of these "variable list files" are in the variables_examples folder. These need to be set and copied into the main directory before the scripts are run.


### Resources for this step
Python library manual: https://shapely.readthedocs.io/en/stable/
Geo-tutorial: https://automating-gis-processes.github.io/2017/lessons/L3/point-in-polygon.html





