import copy
import fiona
from fiona.crs import from_epsg
import geopandas as gpd
import numpy as np
import pysheds
from pysheds.grid import Grid
from shapely.geometry import mapping, Polygon

from .network import Network

class Delineate:
  def __init__(
      self,
      network: Network,
      grid: pysheds.sgrid.sGrid,
      fdir: pysheds.sgrid.sGrid,
      acc: pysheds.sgrid.sGrid,
      grid_epsg: int,
    ):
    '''
    network: stormcatchments.network.Network
      Network object that will be used to drive the networking / infrastructure
      connectivity aspects of catchment delineation
    
    grid: pysheds.sgrid.sGrid
      DEM

    acc: pysheds.sview.Raster
      A pysehds flow accumulation raster

    fdir: pysheds.sview.Raster
      A pysheds flow direction raster

    grid_epsg: None | int
      EPSG code for the CRS of the DEM
    '''
    self.net = network
    self.grid = grid
    self.fdir = fdir
    self.acc = acc
    self.grid_epsg = grid_epsg

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

  def delineate_points(self, pts: gpd.GeoDataFrame, how: str) -> list:
    '''
    Delineate catchments for a subset of infrastructure points
    '''
    if how not in ['inlet', 'outlet']:
      raise ValueError(
        f'"{how}" is an invalid option for "how", must be "inlet" or "outlet"'
      )
    
    pt_coords = pts['geometry'].tolist()

    return


  def get_stormcatchment(self, pour_pt: tuple, acc_thresh: int=1000) -> gpd.GeoSeries:
    '''
    Delineate a stormcatchment
    '''
    catchment = self.get_catchment(pour_pt, acc_thresh)
    self.net.generate_catchment_graphs(catchment)

    while True:
      outlet_pts = self.net.get_outlet_points(catchment)
      print(outlet_pts)
      if not outlet_pts.empty:
        outlet_catchments = self.delineate_points(outlet_pts, how='outlet')
        catchment = gpd.overlay(catchment, outlet_catchments, how='difference')
        catchment = catchment.dissolve()

      inlet_pts = self.net.get_inlet_points(catchment)
      if not inlet_pts.empty:
        inlet_catchments = self.delineate_points(inlet_pts, how='inlet')
        catchment = gpd.overlay(catchment, inlet_catchments, how='union')
        catchment = catchment.dissolve()
        self.net.generate_catchment_graphs(catchment)
      
      if outlet_pts is None and inlet_pts is None:
        # Stormcatchment complete
        break

    return catchment

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
