import geopandas as gpd
import json

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
    pt_x = pt.geometry.x
    pt_y = pt.geometry.y

    # Get all segments that pt touches, could be on a vertex or between verticies
    touch_segs = net.segments.cx[pt_x:pt_x, pt_y:pt_y]

    seg_json = json.loads(touch_segs.geometry.to_json())
    seg_coords = set()
    for f in seg_json['features']:
      for coord in f['geometry']['coordinates']:
        seg_coords.add(tuple(coord))

    if (pt_x, pt_y) not in seg_coords:
      floating_pts.append(pt)
    
  return gpd.GeoDataFrame(floating_pts)

def snap_points(net: Network, tolerance: float) -> None:
  # Snap all floating (un-snapped) points to the nearest line vertex
  pass

def find_multi_outlet(net: Network) -> gpd.GeoDataFrame:
  # Return all subnetworks within the greater Network that have more than one flow
  # source / outlet
  pass
