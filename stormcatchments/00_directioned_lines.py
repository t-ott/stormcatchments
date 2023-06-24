import geopandas as gpd
import matplotlib.pyplot as plt
from network import Network

DATA_GPKG = "/Users/TommyOtt/GIS/_data/GIS_SET_5/GIS_SET_5.gpkg"
lines = gpd.read_file(DATA_GPKG, layer="SW_ClosedConduit_AOI_0")
pts = gpd.read_file(DATA_GPKG, layer="SW_Inlet_AOI_0")
pts["IS_SINK"] = True
pts["IS_SOURCE"] = False

net = Network(
    storm_lines=lines,
    storm_pts=pts,
)

net.resolve_directions(method="vertex_order", verbose=True)
net.leaf_nodes_to_sources()
net.draw()
plt.show()
