import os
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
import rasterio.plot

import delineate
import terrain
from network import Network

ROOT_DIR = Path(os.path.realpath(__file__)).parent.parent
DATA_DIR = ROOT_DIR / "examples" / "example_data" / "gwinnett"
DEM_EPSG = 26916
DEM_PATH = DATA_DIR / "dem_0.tif"

POUR_PT = (782587.9, 3777749.6)

lines = gpd.read_file(DATA_DIR / "sw_closedconduit_0.shp")
lines = lines.to_crs(epsg=DEM_EPSG)
pts = gpd.read_file(DATA_DIR / "sw_inlet_0.shp")
pts = pts.to_crs(epsg=DEM_EPSG)
pts["IS_SINK"] = True
pts["IS_SOURCE"] = False

net = Network(
    storm_lines=lines,
    storm_pts=pts,
)

net.resolve_directions(method="vertex_order", verbose=True)
net.leaf_nodes_to_sources()
# net.draw()
# plt.show()

# raster = rasterio.open(DEM_PATH)
# fig, ax = plt.subplots(figsize=(20, 20))
# rasterio.plot.show(raster, ax=ax)

# net.draw(ax=ax)

grid, acc, fdir = terrain.preprocess_dem(str(DEM_PATH))

delin = delineate.Delineate(net, grid, fdir, acc, DEM_EPSG)

# net.draw()
# plt.show()

catch = delin.get_catchment(POUR_PT, acc_thresh=20)
stormcatch = delin.get_stormcatchment(POUR_PT, acc_thresh=20)

ax = catch.plot()
stormcatch.plot(ax=ax)

plt.show()
