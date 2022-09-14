import copy
import fiona
from fiona.crs import from_epsg
import geopandas as gpd
import numpy as np
import pysheds
from pysheds.grid import Grid
from shapely.geometry import mapping, Polygon

# Force reload, for delevopment
import importlib
import graphs
importlib.reload(graphs)
from graphs import Graphs

STORM_PT_FLOWS = {
    2: 0, # Catchbasin
    3: 2, # Stormwater manhole
    5: 1, # Outfall
    8: 0, # Culvert inlet',
    9: 1, # Culvert outlet'
}

class Delineate:
  def __init__(
      self,
      storm_lines: gpd.GeoDataFrame,
      storm_pts: gpd.GeoDataFrame,
      grid: pysheds.sgrid.sGrid,
      fdir: pysheds.sgrid.sGrid,
      acc: pysheds.sgrid.sGrid,
      grid_epsg: int,
    ):
    '''
    storm_lines: gpd.GeoDataFrame

    storm_pts: gpd.GeoDataFrame
      Needs a column "flow" with integer values representing which direction flow
      travels through the given point type => {0: Flow enters at point, 1: Flow exits 
      at point, 2: Flow neither enters not exits}
    
    grid: pysheds.sgrid.sGrid
      DEM

    acc: pysheds.sview.Raster
        A pysehds flow accumulation raster

    fdir: pysheds.sview.Raster
      A pysheds flow direction raster

    grid_epsg: None | int
      EPSG code for the CRS of the DEM
    '''
    self.storm_lines = storm_lines

    self.storm_pts = storm_pts
    if 'flow' in self.storm_pts.columns:
        flow_vals = self.storm_pts['flow'].unique().tolist()
        assert sorted(flow_vals) == [0, 1, 2], f'Column "flow" in storm_pts' \
                  'must only contain values [0, 1, 2]'
    else:
        self.storm_pts['flow'] = self.storm_pts['Type'].map(STORM_PT_FLOWS).fillna(2)

    # assert 'flow' in storm_pts.columns, 'storm_pts must contain a column named "flow"' \
    #   ' with integer values representing the direction of flow at a given point'
    # self.storm_pts = storm_pts
    self.gen = Graphs(storm_lines, storm_pts)

    self.grid = grid
    self.fdir = fdir
    self.acc = acc
    self.grid_epsg = grid_epsg

  def generate_infra_graphs(self, catchment: gpd.GeoSeries) -> None:
    '''
    Generate graph representations of all infrastructure networks that are within a
    catchment.
    '''
    # ensure CRS match
    if catchment.crs != self.storm_pts.crs:
      catchment = catchment.to_crs(crs=self.storm_pts.crs)

    pts = gpd.clip(self.storm_pts, catchment)
    
    for pt in pts.itertuples(name='StormPoint'):
      downstream_pt = self.gen.find_downstream_pt(pt)
      print('Found downstream point...')
      print(downstream_pt)

      self.gen.add_upstream_pts(downstream_pt)
     # print(pt)

  def get_catchment(self, pour_pt: tuple, acc_thresh: int=1000) -> gpd.GeoSeries:
    """
    Delineate catchment using PySheds

    Parameters
    ----------
    pour_pt: tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    acc_thresh: int=1000
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    list of shapely.Polygon objects
    
    """
    # create a deep copy of the grid to not manipulate original grid
    grid = copy.deepcopy(self.grid)
    x, y = pour_pt
    x_snap, y_snap = grid.snap_to_mask(self.acc > acc_thresh, (x, y))
    catch = grid.catchment(x=x_snap, y=y_snap, fdir=self.fdir)
    grid.clip_to(catch)
    catch_view = grid.view(catch, dtype=np.uint8)
    catch_vec = grid.polygonize(catch_view)
    
    catch_polys = []
    for shape, _ in catch_vec:
        assert shape['type'] == 'Polygon'
        all_poly_coords = shape['coordinates']
        for poly_coords in all_poly_coords:
            catch_polys.append(Polygon(poly_coords))
  
    return gpd.GeoSeries(catch_polys).set_crs(epsg=self.grid_epsg)

  def get_inlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    '''
    Get a GeoDataFrame that contains all the infrastructure points that collect runoff
    that ultimately discharges to the inital pour point.
    '''
    pass

  def delineate_inlet_points(self, inlet_pts: gpd.GeoDataFrame) -> list:
    '''
    Delineate catchments for any infrastructure inlet point that ties into the initial
    catchment.
    '''
    pass


  def poly_to_shp(self, poly, shp_path, epsg):
    schema = {
        'geometry': 'Polygon',
        'properties': {'id': 'int'}
    }
    
    with fiona.open(
        shp_path,
        'w',
        driver='ESRI Shapefile',
        crs=from_epsg(epsg),
        schema=schema
    ) as shp:
        shp.write({
            'geometry': mapping(poly),
            'properties': {'id': 0}
        })