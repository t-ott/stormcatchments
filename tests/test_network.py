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


def test_add_upstream_simple_johnson(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==244244]
  net.add_upstream_pts(downstream_pt)
  net.draw_G()
  print('Getting geom...')
  print(net.G[244244])
  # print(nx.get_node_attributes(net.G, 'geometry')[0])

  assert len(net.G.nodes()) == 3

def test_add_upstream_complex_johnson(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)

  # TODO:
  # How many nodes are there supposed to be?
  

def test_add_upstream_twice_johnson(net):
  # 5 nodes
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)

  # 4 nodes, disconnected from previous subgraph
  downstream_pt = net.pts[net.pts['OBJECTID']==244153]
  net.add_upstream_pts(downstream_pt)

  # assert len(net.G.nodes()) == 9
  # nx.draw(net.G)
  # plt.show()


def test_get_outlet_johnson(net):
  downstream_pt = net.pts[net.pts['OBJECTID']==21134]
  net.add_upstream_pts(downstream_pt)
  assert net.get_outlet(20847) == 21134


def test_find_downstream_simple_johnson(net):
  upstream_pt = net.pts[net.pts['OBJECTID']==245051]
  downstream_pt = net.find_downstream_pt(upstream_pt)
  assert downstream_pt.OBJECTID == 244132


def test_generate_catchment_graphs_johnson(net):
  initial_catchment = gpd.read_file('tests/test_data/initial_catchment.shp')
  net.generate_catchment_graphs(initial_catchment['geometry'])
  print(net.G.nodes())
