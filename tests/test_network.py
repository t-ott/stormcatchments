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


@pytest.fixture
def net_synthetic():
  storm_lines = gpd.read_file('tests/test_data/synthetic/lines.shp')
  storm_pts = gpd.read_file('tests/test_data/synthetic/pts.shp')

  # Cast 0 | 1 integers to bool
  storm_pts['IS_SINK'] = storm_pts['IS_SINK'].astype(bool)
  storm_pts['IS_SOURCE'] = storm_pts['IS_SOURCE'].astype(bool)

  net = network.Network(storm_lines, storm_pts, index_column='id', type_column=None)
  return net


def test_non_empty_graph_johnson(net_johnson):
  '''Ensure Network initialization generates non-empty graph'''
  net = net_johnson
  assert not net.segments.empty
  assert net.G.number_of_nodes() > 0


def test_line_segmentation_johnson(net_johnson):
  '''
  Ensure line segmentation process of Network initialization retains total line length
  within 0.1m
  '''
  net = net_johnson
  assert round(
    net.lines.geometry.length.sum(), 1
  ) == round(
    net.segments.geometry.length.sum(), 1
  )


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
  '''
  After resolving direction for a SINK point, test that it's outlet is properly
  identified
  '''
  net = net_johnson
  outfall_pt = net.pts.loc[21134]
  net.resolve_direction(outfall_pt)
  assert net.get_outlet(20847) == 21134


def test_find_downstream_simple_johnson(net_johnson):
  '''Ensure the proper downstream point is found for a SINK point'''
  net = net_johnson
  upstream_pt = net.pts.loc[245051]
  downstream_pt = net.find_downstream_pt(upstream_pt)
  assert downstream_pt.Index == 244132


def test_resolve_catchment_graphs_johnson(net_johnson):
  '''
  Test that resolve_catchment_graph removes all bidirectional edges within the
  catchment, meaning the flow directions for the catchment subgraph have been fully
  resolved / have no ambiguity 
  '''
  net = net_johnson
  catchment = gpd.read_file('tests/test_data/johnson_vt/initial_catchment.shp')
  net.resolve_catchment_graph(catchment)

  # Check each point within the catchment to ensure it has no bidirectional edges
  catchment = catchment.to_crs(net.crs)
  catchment_pts = gpd.clip(net.pts, catchment)
  for pt in catchment_pts.itertuples('StormPoint'):
    x, y = network.get_point_coords(pt.geometry)
    predecessors = [u for u in net.G.predecessors((x, y))]
    successors = [v for v in net.G.successors((x, y))]
    # There should be no nodes that are both predecessors and successors
    assert len(set(predecessors).intersection(successors)) == 0


def test_consec_out_snyth(net_synthetic):
  '''Test simple graph with two consecutive SOURCE/outfall points'''
  net = net_synthetic
  second_out_pt = net.pts.loc[13]
  net.resolve_direction(second_out_pt)
  first_out_pt_coords = tuple([net.pts.loc[14].geometry.x, net.pts.loc[14].geometry.y])
  successors = [v for v in net.G.successors(first_out_pt_coords)]
  assert len(successors) == 1
