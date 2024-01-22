# Resources:
# https://automating-gis-processes.github.io/2017/lessons/L3/point-in-polygon.html
# https://shapely.readthedocs.io/en/stable/



# Library to work with Shapefiles
# pip3 install pyshp
# pip3 install shapely

############################################################
# 1. Libraries
############################################################
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import geojson
import pyproj


# Paths to files are stored in a seperate python files, so that they are not commited to git
from variables_pip import polygon_p


############################################################
# 2. Data imports

# Import the boundaries file
## NOTICE: depending on the structure of the file, this may need tweaking. We want x,y coordinates of points making up the polygon.
with open(polygon_p) as polygon:
    poly_coords = geojson.load(polygon)

polygon = poly_coords['features'][0]['geometry']['coordinates']
#print(polygon)

# The projection of coordinates needs to be known. In case they are not EPSG:27700, they will need to be converted.
epsg_3857 = pyproj.CRS('EPSG:3857')
epsg_27700 = pyproj.CRS('EPSG:27700')

# Create an array of tuples making up the polygon
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
print(pgon)

# points



############################################################

# Since for the parish maps, we will have one polygon, and may points (OA centroids), it makes sense to read check if polygon contains the point.
# The result only outputs OA that exist within given polygon.

############################################################
# 3. 



############################################################


