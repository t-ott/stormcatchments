# stormcatchments
## Stormwater network aware catchment delineation

Converts existing stormwater infrastucture GIS feature data (points and lines) into a
```networkx``` directed graph (```DiGraph```) object, then utilizes the ```DiGraph``` to
incorporate subsurface flows into urban stormwater catchment delineation.

In development, currently only configured for [Vermont Agency of Natural Resources stormwater infrastructure data](https://gis-vtanr.hub.arcgis.com/maps/VTANR::stormwater-infrastructure/explore?location=43.609172%2C-72.968811%2C14.15).

Various dependencies include:
- ```geopandas```
- ```networkx```
- ```pysheds```

Similar libraries/projects:
- [```s2g```](https://github.com/caesar0301/s2g)
- [```networkx``` module ```nx_shp.py```](https://github.com/networkx/networkx/blob/6e20b952a957af820990f68d9237609198088816/networkx/readwrite/nx_shp.py)

## Determining subsurface flow direction
Flow direction of stormwater infrastructure can be assumed  by backtracing a network
from it's outfall/discharge point. It is assumed that flow from all points that connect
to said discharge point ultimately are directed to it. If a network has mutliple
outfalls/discharge points, determining subsurface flow direction becomes unclear, or
impossible, without additional input data (pipe elevations, etc.). Ground-level
elevations of catchbasins and manholes (rim elevations) could be used as a analog for
pipe elevations in these scenarios. **This is not yet implemented here**. This would
require sampling elevation raster values as the coordinates of each basin/manhole, then
writing edge directions toward the farthest downhill connection between each node.
However, in reality, pipe gradients do not necessarily follow the gradient of the ground
surface.

## Example Usage

### Imports
```python
import geopandas as gpd
from stormcatchments import delineate, network, terrain
```
### Read infrastructure data
```python
storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
```
### Initialize Network object
```python
net = network.Network(storm_lines, storm_pts)
net.resolve_directions(method='from_sources')
```
### Preprocess terrain data
```python
grid, fdir, acc = terrain.preprocess_dem('tests/test_data/johnson_vt/dem.tif')
```
### Initialize Delineate object and get a stormcatchment
```python
grid_epsg = 6589
delin = delineate.Delineate(net, grid, fdir, acc, grid_epsg)

# (x, y) coordinates in same CRS as grid
pour_pt = (484636, 237170)
stormcatchment = delin.get_stormcatchment(pour_pt)
```
