import geopandas as gpd
import pytest
from stormcatchments import network

@pytest.fixture
def net():
  storm_lines = gpd.read_file('tests/test_data/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)
  return net


def test_add_upstream_pts_once(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)
  assert len(net.G.nodes()) == 5


def test_add_upstream_pts_twice(net):
  # 5 nodes
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)

  # 4 nodes, disconnected from previous subgraph
  downstream_pt = net.pts[net.pts['OBJECTID']==244153]
  net.add_upstream_pts(downstream_pt)

  assert len(net.G.nodes()) == 9


def test_get_outlet(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)
  assert net.get_outlet(20847) == 21134


def test_find_downstream_pt_culvert(net):
  upstream_pt = net.pts[net.pts['OBJECTID']==245051]
  downstream_pt = net.find_downstream_pt(upstream_pt)
  assert downstream_pt.OBJECTID == 244132


def test_generate_catchment_graphs(net):
  initial_catchment = gpd.read_file('tests/test_data/initial_catchment.shp')
  net.generate_catchment_graphs(initial_catchment['geometry'])
  print(net.G.nodes())