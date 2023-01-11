from copy import deepcopy

import geopandas as gpd
from shapely.geometry import Point

from stormcatchments.network import Network


def find_floating_points(net: Network) -> gpd.GeoDataFrame:
  '''
  Find and return any points in a Network that are not snapped to a line vertex. These
  floating points cannot be integrated into networking functionality unless they are
  snapped to a line vertex.

  Parameters
  ----------
  net : Network
    A stormcatchments Network object whose point data will be inspected for floating
    points

  Returns
  -------
  floating_pts : gpd.GeoDataFrame
    A GeoDataFrame of any floating points in net.pts
  '''
  floating_pts = []
  for pt in net.pts.itertuples():
    # Get all segments that pt touches, could be on a vertex or between verticies
    touch_segs = net.segments[net.segments.geometry.touches(pt.geometry)]

    if len(touch_segs) == 0:
      floating_pts.append(pt)
      continue

    # Collect segment coordinates as (x, y) tuples
    seg_coords = set()
    for l in touch_segs.geometry:
      for c in l.coords:
        seg_coords.add(c)

    if (pt.geometry.x, pt.geometry.y) not in seg_coords:
      floating_pts.append(pt)
  
  return gpd.GeoDataFrame(floating_pts, crs=net.crs).set_index('Index')

def snap_points(net: Network, tolerance: float) -> Network:
  '''
  Create a copy of a supplied Network which snaps any points in Network to the
  closest line vertex within a snapping tolerance

  Parameters
  ----------
  net : Network
    A stormcatchments Network object which may contain floating points

  tolerance : float
    The maximum search distance to find the nearest vertex

  Returns
  -------
  net_snapped : Network
    A stormcatchments Network object with snapping applied to its point data
  '''
  # Snap all floating (un-snapped) points to the nearest line vertex
  pass

def find_multi_outlet(net: Network) -> gpd.GeoDataFrame:
  # Return all subnetworks within the greater Network that have more than one flow
  # source / outlet
  pass
