import copy
import geopandas as gpd
import numpy as np
import pysheds
from shapely.geometry import Polygon

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

    grid_epsg: int
      EPSG code for the CRS of the DEM
    '''
    self.net = network
    self.grid = grid
    self.fdir = fdir
    self.acc = acc
    self.grid_epsg = grid_epsg

  def get_catchment(self, pour_pt: tuple, acc_thresh: int=1000) -> gpd.GeoDataFrame:
    '''
    Delineate catchment using pysheds

    Parameters
    ----------
    pour_pt: tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    acc_thresh: int=1000
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    catchment: gpd.GeoDataFrame
      A GeoDataFrame containing the newly delineated catchment polygon
    '''
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
  
    return gpd.GeoDataFrame(
      {'geometry': gpd.GeoSeries(catch_polys).set_crs(epsg=self.grid_epsg)}
    )

  def delineate_points(
    self, pts: gpd.GeoDataFrame, delineated_oids: set
  ) -> tuple([gpd.GeoDataFrame, set]):
    '''
    Delineate catchments for a subset of infrastructure points

    Parameters
    ----------
    pts: gpd.GeoDataFrame
      Points to delineate catchments for
    
    delineated_oids: set
      A set of the OBJECTID (indicies) of point that have already been delineated. These
      points may or may not lie spatially within the catchment because snapping to the
      flow accumulation raster may shift their location

    Returns
    -------
    catchments: gpd.GeoDataFrame
      The newly delineated catchment for all the provided points, or an empty
      GeoDataFrame if the provided points have already been delineated
    
    delineated_oids: set
      (Same as Parameter delineated_oids, see above)
    '''
    catchments = gpd.GeoDataFrame()

    for pt in pts.itertuples():
      if pt.Index in delineated_oids:
        continue
      else:
        delineated_oids.add(pt.Index)
        pt_catchment = self.get_catchment((pt.geometry.x, pt.geometry.y))
        catchments = catchments.append(pt_catchment)

    if not catchments.empty:
      catchments = catchments.set_crs(epsg=self.grid_epsg)

    return catchments, delineated_oids


  def get_stormcatchment(self, pour_pt: tuple, acc_thresh: int=1000) -> gpd.GeoDataFrame:
    '''
    Iteratively delineate a stormcatchment. pysheds does the delineation work and
    the network module provides the stormwater infrastructure networking

    Parameters
    ----------
    pour_pt: tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    acc_thresh: int=1000
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    catchment: gpd.GeoDataFrame
      A GeoDataFrame containing the newly delineated catchment polygon
    '''
    catchment = self.get_catchment(pour_pt, acc_thresh)
    self.net.generate_catchment_graphs(catchment)

    delineated_oids = set()

    while True:
      outlet_pts = self.net.get_outlet_points(catchment)
      if not outlet_pts.empty:
        outlet_catchments, delineated_oids = self.delineate_points(
          outlet_pts, delineated_oids, how='outlet'
        )
        if not outlet_catchments.empty:
          catchment = gpd.overlay(
            catchment, outlet_catchments, how='difference'
          ).set_crs(epsg=self.grid_epsg)
          catchment = catchment.dissolve()
        else:
          # empty outlet_pts
          outlet_pts = gpd.GeoDataFrame()

      inlet_pts = self.net.get_inlet_points(catchment)
      if not inlet_pts.empty:
        inlet_catchments, delineated_oids = self.delineate_points(
          inlet_pts, delineated_oids, how='inlet'
        )
        if not inlet_catchments.empty:
          catchment = gpd.overlay(
            catchment, inlet_catchments, how='union'
          ).set_crs(epsg=self.grid_epsg)
          catchment = catchment.dissolve()
          self.net.generate_catchment_graphs(catchment)
        else:
          # empty inlet_pts
          inlet_pts = gpd.GeoDataFrame()
      
      if outlet_pts.empty and inlet_pts.empty:
        # stormcatchment complete
        break

    return catchment
