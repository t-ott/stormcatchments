import geopandas as gpd
import pytest

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

from stormcatchments import network

@pytest.fixture
def net_johnson():
  storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)
  return net


def test_add_upstream_simple_johnson(net_johnson):
  downstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==244244]
  net_johnson.add_upstream_pts(downstream_pt)
  net_johnson.draw_G()
  # print('Getting geom...')
  # print(net_johnson.G[244244])
  # print(nx.get_node_attributes(net.G, 'geometry')[0])

  assert len(net_johnson.G.nodes()) == 3

def test_add_upstream_complex_johnson(net_johnson):
  downstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==21134]
  net_johnson.add_upstream_pts(downstream_pt)

  net_johnson.draw_G()
  # TODO:
  # How many nodes are there supposed to be?
  

def test_add_upstream_twice_johnson(net_johnson):
  # 5 nodes
  downstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==21134]
  net_johnson.add_upstream_pts(downstream_pt)

  # 4 nodes, disconnected from previous subgraph
  downstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==244153]
  net_johnson.add_upstream_pts(downstream_pt)

  # assert len(net_johnson.G.nodes()) == 9
  # nx.draw(net_johnson.G)
  # plt.show()


def test_get_outlet_johnson(net_johnson):
  downstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==21134]
  net_johnson.add_upstream_pts(downstream_pt)
  assert net_johnson.get_outlet(20847) == 21134


def test_find_downstream_simple_johnson(net_johnson):
  upstream_pt = net_johnson.pts[net_johnson.pts['OBJECTID']==245051]
  downstream_pt = net_johnson.find_downstream_pt(upstream_pt)
  assert downstream_pt.OBJECTID == 244132


def test_generate_catchment_graphs_johnson(net_johnson):
  initial_catchment = gpd.read_file('tests/test_data/johnson_vt/initial_catchment.shp')
  net_johnson.generate_catchment_graphs(initial_catchment['geometry'])
  print(net_johnson.G.nodes())
