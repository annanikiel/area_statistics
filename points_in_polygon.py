
# Given a polygon and points, this script outputs and exports a list of points inside the polygon.

############################################################
# 1. Libraries
############################################################
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import geojson
import pyproj


# Variables used in this file
from variables_examples.variables_pip_example import polygon_p


############################################################
# 2. Polygon

# Import the boundaries file
## NOTICE: depending on the format and structure of the file, this may need tweaking. 
## We want x,y coordinates of points making up the polygon in the same projection as points in next step.
## ESPG:27700 is used throughout this project

with open(polygon_p) as polygon:
    poly_coords = geojson.load(polygon)

polygon = poly_coords['features'][0]['geometry']['coordinates']
#print(polygon)

# The projection of coordinates needs to be known. (In this case it is ESPG:3857)
# In case they are not EPSG:27700, they will need to be converted.
epsg_3857 = pyproj.CRS('EPSG:3857')
epsg_27700 = pyproj.CRS('EPSG:27700')

# Create the polygon
## NOTICE: This may need tweaking depending on the file structure
coords = [];
for x in polygon:
    for y in x:
        for point in y:
            p_epsg_3857 = Point(point[0], point[1])
            project =  pyproj.Transformer.from_crs(epsg_3857, epsg_27700, always_xy=True).transform
            point = transform(project,p_epsg_3857)

            # May need to convert tuples into points
            
            coords.append(point)

#print(coords)

# Define polygon
pgon = Polygon(coords)
# print(pgon)


############################################################

# Since for the parish maps, we will have one polygon, and may points (OA centroids), it makes sense to read check if polygon contains the point.
# The result is a list of OA which centroid fall within the extend of a given boundary with an information to indicate if they are within the polygon, or not.

############################################################

# Determine extent of the polygon - only import points within it
# The aim is to narrow down the number of points we need to check are in the polygon; Min / max coords check will be faster than contains operation on all points
# This can be done as they are being imported
# At this point OA identifier and ID are retained.


# Of these within the extend, check which are within the polygon itself.
# Output two lists - TRUE (in polygon); FALSE - not in polygon.



# Sense check - draw polygon and TRUE / FALSE OAs with their centroids to make sure the script worked as expected


# Remerge the OA names back to the points

# The final output is a list (JSON) of OAs making inside a given area.



############################################################


