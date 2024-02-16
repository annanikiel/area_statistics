
# Given a polygon and points, this script outputs and exports a list of points inside the polygon.

############################################################
# 1. Libraries
############################################################
#from shapely.geometry import Point, Polygon
from shapely import Point, Polygon, contains
from shapely.ops import transform
import geojson
import pyproj
import folium

import csv


# Variables used in this file
from variables_pip import polygon_p, points_file


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
# print(pgon.area)
# print (pgon.bounds)


############################################################

# Since for the parish maps, we will have one polygon, and may points (OA centroids), it makes sense to read check if polygon contains the point.
# The result is a list of OA which centroid fall within the extend of a given boundary with an information to indicate if they are within the polygon, or not.

############################################################

# Determine extent of the polygon - only import points within it + 300m buffer zone
extent = pgon.bounds
# Result: (378509.3723922186, 397460.89025646896, 381811.71099850745, 399914.02726411185)
# Definition: (minx, miny, maxx, maxy)

# Since ESPG:27700 operates in meters, we can simply add 300 meters to the coordinates/
minx = extent[0] + 300
miny = extent[1] + 300
maxx = extent[2] + 300
maxy = extent[3] + 300

# buffer zone may need to be a veriable - as the size will need to be different,depending on the shape size.

# Import a CSV with OA centroids (from ONS)
# This code also converts the strings from CSV into floats, for numerical comparisons
# Only points within the polygon extent are extracted (although all are checked)

OA = []
with open(points_file) as fp:
    reader = csv.reader(fp, delimiter=",", quotechar='"')
    next(reader, None)  # skip the headers

    for row in reader:
        x = float(row[3])
        y = float(row[4])

        if x >= minx and x <= maxx and y >= miny and y <= maxy:
            OA.append([row[1],x,y])

#print(OA)
print(len(OA))



# The aim is to narrow down the number of points we need to check are in the polygon; Min / max coords check will be faster than contains operation on all points
# This can be done as they are being imported
# At this point OA identifier and ID are retained.


# Of these within the extend, check which are within the polygon itself.
OA_poly = []
for item in OA:
    id = item[0]
    point_val = [item[1],item[2]]
    point_geom = Point(item[1],item[2])

    # Only output points in polygon
    if contains(pgon,point_geom):
        OA_poly.append([id,point_val])

#print(OA_poly);
print(len(OA_poly))


# Check the difference between two lists (with uncommented print((len(list)))
# OA_poly contains our final list.

# Sense check - draw polygon and TRUE / FALSE OAs with their centroids to make sure the script worked as expected.
# 
m = folium.Map(location=(45.5236, -122.6750))
m.save("index.html")

# Remerge the OA names back to the points

# The final output is a list (JSON) of OAs making inside a given area.



############################################################


