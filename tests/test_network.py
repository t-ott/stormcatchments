import geopandas as gpd
import networkx as nx
import pytest

from stormcatchments import network

@pytest.fixture
def net_johnson():
  storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
  storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
  net = network.Network(storm_lines, storm_pts)
  return net


def test_init_johnson(net_johnson):
  '''Ensure Network initialization generates non-empty graph'''
  net = net_johnson
  assert not net.segments.empty
  assert net.G.number_of_nodes() > 0


def test_points_in_graph_johnson(net_johnson):
  '''Ensure coordinates of various storm_points are present as nodes within the graph'''
  net = net_johnson
  for idx in [20845, 244244, 21135, 244947, 244275]:
    x, y = network.get_point_coords(net.pts.loc[idx].geometry)
    assert net.G.has_node((x, y))


def test_resolve_direction_simple_johnson(net_johnson):
  '''
  Ensure the direction of a simple 3-node subgraph can be resolved such that the only
  edges present are in the correct direction of flow for that subgraph
  '''
  net = net_johnson
  outfall_pt = net.pts.loc[244244]
  net.resolve_direction(outfall_pt)

  edges = {244374: 244244, 244900: 244374}
  for u, v in edges.items():
    u_x, u_y = network.get_point_coords(net.pts.loc[u].geometry)
    v_x, v_y = network.get_point_coords(net.pts.loc[v].geometry)
    # Edge is present in correct direction of flow
    assert net.G.has_edge((u_x, u_y), (v_x, v_y))
    # Edge is not present in reverse of flow direction
    assert not net.G.has_edge((v_x, v_y), (u_x, u_y))


def test_resolve_direction_complex_johnson(net_johnson):
  '''
  Ensure the direction of a larger subgraph with multiple branches can be resolved such
  that the only edges present are in the correct direction of flow for that subgraph
  '''
  net = net_johnson
  outfall_pt = net.pts.loc[21134]
  net.resolve_direction(outfall_pt)
  
  edges = {20845: 21134, 20846: 20845, 20847: 20846, 21135: 20845}
  for u, v in edges.items():
    u_x, u_y = network.get_point_coords(net.pts.loc[u].geometry)
    v_x, v_y = network.get_point_coords(net.pts.loc[v].geometry)
    # Edge is present in correct direction of flow
    assert net.G.has_edge((u_x, u_y), (v_x, v_y))
    # Edge is not present in reverse of flow direction
    assert not net.G.has_edge((v_x, v_y), (u_x, u_y))


def test_get_outlet_johnson(net_johnson):
  net = net_johnson
  outfall_pt = net.pts.loc[21134]
  net.resolve_direction(outfall_pt)
  assert net.get_outlet(20847) == 21134


def test_find_downstream_simple_johnson(net_johnson):
  net = net_johnson
  upstream_pt = net.pts.loc[245051]
  downstream_pt = net.find_downstream_pt(upstream_pt)
  assert downstream_pt.Index == 244132


# def test_generate_catchment_graphs_johnson(net_johnson):
#   initial_catchment = gpd.read_file('tests/test_data/johnson_vt/initial_catchment.shp')
#   net_johnson.generate_catchment_graphs(initial_catchment['geometry'])
#   pt_types = [
#     pt_type for _, pt_type in nx.get_node_attributes(net_johnson.G, 'Type').items()
#   ]
#   # 3 catchbasins
#   assert pt_types.count(2) == 3
#   # 3 culvert outlets
#   assert pt_types.count(9) == 3
