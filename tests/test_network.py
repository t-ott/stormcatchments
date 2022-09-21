import geopandas as gpd
import pytest
from stormcatchments import network

@pytest.fixture
def net():
  storm_lines = gpd.read_file('tests/test_data/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)
  return net

def test_add_upstream_pts(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)
  assert len(net.Gs[0].nodes()) == 5
  assert net.Gs[0].out_degree()[21134] == 0

def test_find_downstream_pt_culvert(net):
  upstream_pt = net.pts[net.pts['OBJECTID']==245051]
  downstream_pt = net.find_downstream_pt(upstream_pt)
  assert downstream_pt.OBJECTID == 244132
