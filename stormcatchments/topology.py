import geopandas as gpd
from stormcatchments.network import Network

def find_floating_points(net: Network) -> gpd.GeoDataFrame:
  # Return all points that are not snapped to a line vertex
  pass

def snap_points(net: Network, tolerance: float) -> None:
  # Snap all floating (un-snapped) points to the nearest line vertex
  pass

def find_multi_outlet(net: Network) -> gpd.GeoDataFrame:
  # Return all subnetworks within the greater Network that have more than one flow
  # source / outlet
  pass
