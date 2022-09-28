import geopandas as gpd
from pysheds.grid import Grid
import pytest

from stormcatchments import network, delineate

@pytest.fixture
def delineate_johnson():
  # construct Network
  storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)

  # pysheds DEM loading, conditioning, and preprocessing
  grid = Grid.from_raster('tests/test_data/johnson_vt/dem.tif')
  dem = grid.read_raster('tests/test_data/johnson_vt/dem.tif')
  pit_filled = grid.fill_pits(dem)
  flooded = grid.fill_depressions(pit_filled)
  inflated = grid.resolve_flats(flooded)
  fdir = grid.flowdir(inflated)
  acc = grid.accumulation(fdir)

  return delineate.Delineate(net, grid, fdir, acc, 6589)

def test_get_catchment(delineate_johnson):
  pour_pt = (484636, 237170)
  catchment = delineate_johnson.get_catchment(pour_pt)
  assert round(catchment.area.values[0], 1) == 6796.3

