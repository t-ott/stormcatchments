import geopandas as gpd
from shapely.geometry import Point
import pytest

from stormcatchments import network, delineate, terrain

@pytest.fixture
def delineate_johnson():
  # construct Network
  storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)
  net.resolve_directions()

  # pysheds DEM loading, conditioning, and preprocessing
  grid, fdir, acc = terrain.preprocess_dem('tests/test_data/johnson_vt/dem.tif')

  return delineate.Delineate(net, grid, fdir, acc, 6589)


def test_get_catchment(delineate_johnson):
  delin = delineate_johnson
  pour_pt = (484636, 237170)
  catchment = delin.get_catchment(pour_pt)
  assert round(catchment.area.values[0]) == 6796


def test_get_stormcatchment(delineate_johnson):
  delin = delineate_johnson
  pour_pt = (484636, 237170)
  stormcatchment = delin.get_stormcatchment(pour_pt)
  stormcatchment_geom = stormcatchment.iloc[0].geometry

  contain_coords = [(484700, 237490), (484696, 237272)]
  for coords in contain_coords:
    assert stormcatchment_geom.contains(Point(coords))

  not_contain_coords = [(484590, 237200), (484750, 237330)]
  for coords in not_contain_coords:
    assert not stormcatchment_geom.contains(Point(coords))
