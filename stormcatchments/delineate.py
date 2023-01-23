from copy import deepcopy

import geopandas as gpd
import numpy as np
import pysheds
from shapely.geometry import Polygon

from stormcatchments.network import Network

def get_catchment(
  pour_pt: tuple,
  grid: 'pysheds.sgrid.sGrid',
  fdir: 'pysheds.sview.Raster',
  acc: 'pysheds.sview.Raster',
  grid_epsg: int,
  acc_thresh: int=1000
) -> gpd.GeoDataFrame:
    '''
    Delineate catchment using pysheds

    Parameters
    ----------
    pour_pt : tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    grid : pysheds.sgrid.sGrid
      DEM
    
    fdir : pysheds.sview.Raster
      A pysheds flow direction raster

    acc : pysheds.sview.Raster
      A pysehds flow accumulation raster

    grid_epsg : int
      EPSG code for the CRS of the DEM

    acc_thresh : int (default 1000)
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    catchment : gpd.GeoDataFrame
      A GeoDataFrame containing the newly delineated catchment polygon
    '''
    # create a deepcopy of the grid to not manipulate original grid
    grid = deepcopy(grid)
    x, y = pour_pt
    x_snap, y_snap = grid.snap_to_mask(acc > acc_thresh, (x, y))
    catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir)
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
      {'geometry': gpd.GeoSeries(catch_polys).set_crs(epsg=grid_epsg)}
    )


class Delineate:
  def __init__(
      self,
      network: Network,
      grid: 'pysheds.sgrid.sGrid',
      fdir: 'pysheds.sview.Raster',
      acc: 'pysheds.sview.Raster',
      grid_epsg: int,
    ):
    '''
    network : stormcatchments.network.Network
      Network object that will be used to drive the networking / infrastructure
      connectivity aspects of catchment delineation
    
    grid : pysheds.sgrid.sGrid
      DEM

    fdir : pysheds.sview.Raster
      A pysheds flow direction raster

    acc : pysheds.sview.Raster
      A pysehds flow accumulation raster

    grid_epsg : int
      EPSG code for the CRS of the DEM
    '''

    if not network.directions_resolved:
      raise ValueError(
        f'Cannot generate stormcatchment until graph directions of the Network are '
        'resolved'
      )
      
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
    pour_pt : tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    acc_thresh : int (default 1000)
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    catchment : gpd.GeoDataFrame
      A GeoDataFrame containing the newly delineated catchment polygon
    '''
    return get_catchment(
      pour_pt, self.grid, self.fdir, self.acc, self.grid_epsg, acc_thresh=acc_thresh
    )


  def delineate_points(
    self, pts: gpd.GeoDataFrame, delineated: set
  ) -> tuple([gpd.GeoDataFrame, set]):
    '''
    Delineate catchments for a subset of infrastructure points

    Parameters
    ----------
    pts : gpd.GeoDataFrame
      Points to delineate catchments for
    
    delineated : set
      A set of the OBJECTID (indicies) of point that have already been delineated. These
      points may or may not lie spatially within the catchment because snapping to the
      flow accumulation raster may shift their location

    Returns
    -------
    catchments : gpd.GeoDataFrame
      The newly delineated catchment for all the provided points, or an empty
      GeoDataFrame if the provided points have already been delineated
    
    delineated : set
      (Same as param delineated, see above)
    '''
    catchments = gpd.GeoDataFrame()

    for pt in pts.itertuples(name='StormPoint'):
      if pt.Index in delineated:
        continue
      else:
        delineated.add(pt.Index)
        x = pt.geometry.x
        y = pt.geometry.y
        pt_catchment = self.get_catchment((x, y))
        catchments = gpd.pd.concat([catchments, pt_catchment], ignore_index=True)

    if not catchments.empty:
      catchments = catchments.set_crs(epsg=self.grid_epsg)

    return catchments, delineated


  def get_stormcatchment(
    self, pour_pt: tuple, acc_thresh: int=1000
  ) -> gpd.GeoDataFrame:
    '''
    Iteratively delineate a stormcatchment. pysheds does the delineation work and
    the network module provides the stormwater infrastructure networking

    Parameters
    ----------
    pour_pt : tuple
      An (x, y) coordinate pair, with the same coordinate system as the grid

    acc_thresh : int (default 1000)
      The minimum accumulation threshold used during pour point snapping
    
    Returns
    -------
    catchment: gpd.GeoDataFrame
      A GeoDataFrame containing the newly delineated catchment polygon
    '''
    catchment = self.get_catchment(pour_pt, acc_thresh)

    # Keep track of all point indicies which have been delineated
    delineated = set()

    while True:
      outlet_pts = self.net.get_outlet_points(catchment)
      if not outlet_pts.empty:
        outlet_catchments, delineated = self.delineate_points(
          outlet_pts, delineated
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
        inlet_catchments, delineated = self.delineate_points(
          inlet_pts, delineated
        )
        if not inlet_catchments.empty:
          catchment = gpd.overlay(
            catchment, inlet_catchments, how='union', keep_geom_type=False
          ).set_crs(epsg=self.grid_epsg)
          catchment = catchment.dissolve()
        else:
          # empty inlet_pts
          inlet_pts = gpd.GeoDataFrame()
      
      if outlet_pts.empty and inlet_pts.empty:
        # stormcatchment complete
        break

    return catchment
