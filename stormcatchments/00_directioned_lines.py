import geopandas as gpd
from network import Network

DATA_GPKG = "/Users/TommyOtt/GIS/_data/GIS_SET_5/GIS_SET_5.gpkg"
lines = gpd.read_file(DATA_GPKG, layer="SW_ClosedConduit", rows=1000)
pts = gpd.read_file(DATA_GPKG, layer="SW_Inlet", rows=1000)
pts['IS_SINK'] = True
pts['IS_SOURCE'] = False

net = Network(
    storm_lines=lines,
    storm_pts=pts,
)
