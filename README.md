# Area statistics
This project aims to provide a set of python files that can be used to calculate area statistics.
It's particular application here is to generate statistics for the local parish.

# Steps

## Step 1: Geography data - Polygon
In order to calculate the statistics for an arbitrary area (i.e. not the one already defined by ONS), we need to firsly have access to digitised boundary of the said area. Then the statistical geographies contained by the given boundary need to be found. ONS Output Areas (OA) are very small - covering up to 100 households, so can be used to approximate the arbitray area relatively well.

points_in_polygon.py file can be used to generate the list of OA approximating given area. This list can then be used to match census data and perform analysis.
Firstly, the polygon data needs to be imported. Python can handle many different formats with external libraries. Depending on the format and structure of the file, the code may need to be adjusted. The aim is to extract the list of points and convert them, if needed to EPSG 27700 projection, as this is what is used in the UK by ONS and Ordnance Survey, and works best when printing maps / presenting them in documents.
(For any presentation in online maps - EPSG 3857 needes to be used.

The output of Step 1 should be a POLYGON.

Sources: https://shapely.readthedocs.io/en/stable/

## Step 2: Geographt data  - Points
In this example, we are using Census 2021 OA weighted centroids as provided by the ONS. They are using the EPSG 27700 projection.
...


