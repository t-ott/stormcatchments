# stormcatchments
## Stormwater network aware catchment delineation

Converts existing stormwater infrastucture GIS feature data (points and lines) into a
```networkx``` directed graph (```DiGraph```) object, then utilizes the ```DiGraph``` to
incorporate subsurface flows into urban stormwater catchment delineation.

Various dependencies include:
- ```geopandas```
- ```networkx```
- ```pysheds```

Similar libraries/projects:
- [```s2g```](https://github.com/caesar0301/s2g)
- [```networkx``` module ```nx_shp.py```](https://github.com/networkx/networkx/blob/6e20b952a957af820990f68d9237609198088816/networkx/readwrite/nx_shp.py)


## Input data requirements

To utilize this package, you need both **point** and **line** spatial data, which could represent a network of catchbasins and stormlines. The format does not matter as long as it can be successfully read into a ```geopandas.GeoDataFrame```. The line data must connect to the points, and lines must have verticies snapped to the points.
This was initially developed for [Vermont Agency of Natural Resources stormwater infrastructure dataset](https://gis-vtanr.hub.arcgis.com/maps/VTANR::stormwater-infrastructure/explore?location=43.609172%2C-72.968811%2C14.15), so some default parameters (such as the mapping of ```IS_SINK``` and ```IS_SOURCE``` in point data) are configured specifically for this dataset. However, the package should be usable for other datasets.


## Mapping ```IS_SINK``` and ```IS_SOURCE```

Flow sinks are where flow can enter a subsurface system (such as a catchbasin). Flow sources are where flow can exit a subsurface system (such as an outfall). Initializing the ```network.Network``` requires either:
- Defining a ```type_column``` in the point data, then supplying a ```list``` of ```sink_types``` and a ```list``` of ```source_types``` to lookup in the ```type_column```. This will then be mapped onto two ```bool``` columns in the point data named ```IS_SINK``` and ```IS_SOURCE```.
- Manually setting two ```bool``` columns in the point ```GeoDataFrame```, named ```IS_SINK``` and ```IS_SOURCE``` that are set to ```True``` if a point falls into either category.


## Determining subsurface flow direction

Resolving the flow direction of subsurface stormwater networks, which is doing during ```network.Network.resolve_directions()```, can be done in three ways:
1) ```from_sources```: This is the default. This method traces networks upstream from their discharge points. This assumes 
2) ```vertex_order```: This defines the subsurface flow direction using the order of verticies in the line data (flowing from the first to last vertex).
3) ```vertex_order_r```: This is the same as above, but in reverse (flowing from last to first vertex).

Two other potential methods that are not yet implemented are:
- Using surface elevation data as an analog for for subsurface pipe elevations. In flat urban settings this would likely have a lot of issues/inaccuracies.
- Using pipe invert data from the attributes of point or line data. This would require manual preparation by the user but would be the most accurate method.


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
### Also get the original catchment (network unaware) to compare results
```python
catchment = delineate.get_catchment(pour_pt, grid, fdir, acc, 6589)
```
### Plot original catchment in blue and stormcatchment in orange
This uses the built-in ```net.draw()``` method, which adds a ```contextily``` basemap when ```add_basemap=True```.
```python
fig, ax = plt.subplots(figsize=(8, 8))
stormcatchment.plot(ax=ax, ec='orange', fc='orange', alpha=0.7, linewidth=3)
catchment.plot(ax=ax, ec='blue', fc='blue', alpha=0.7, linewidth=3)
net.draw(ax=ax, add_basemap=True)
```
![Plot of catchment and stormcatchment](img/example_stormcatchment.png)