import geopandas as gpd
import networkx as nx
import pytest

from stormcatchments import network
from stormcatchments.constants import SINK_TYPES_VT, SOURCE_TYPES_VT

@pytest.fixture
def net_johnson():
  storm_lines = gpd.read_file('tests/test_data/johnson_vt/storm_lines.shp')
  storm_lines.set_index('OBJECTID', inplace=True)
  storm_pts = gpd.read_file('tests/test_data/johnson_vt/storm_pts.shp')
  storm_pts.set_index('OBJECTID', inplace=True)
  net = network.Network(
    storm_lines,
    storm_pts,
    type_column='Type',
    sink_types=SINK_TYPES_VT,
    source_types=SOURCE_TYPES_VT
  )
  return net


@pytest.fixture
def net_synthetic():
  storm_lines = gpd.read_file('tests/test_data/synthetic/lines.shp')
  storm_pts = gpd.read_file('tests/test_data/synthetic/pts.shp')
  storm_pts.set_index('id', inplace=True)

  # Cast 0 | 1 integers to bool
  storm_pts['IS_SINK'] = storm_pts['IS_SINK'].astype(bool)
  storm_pts['IS_SOURCE'] = storm_pts['IS_SOURCE'].astype(bool)

  net = network.Network(storm_lines, storm_pts)
  return net


def test_non_empty_graph_johnson(net_johnson):
  '''Ensure Network initialization generates non-empty graph'''
  net = net_johnson
  net.resolve_directions()
  assert not net.segments.empty
  assert net.G.number_of_nodes() > 0


def test_line_segmentation_johnson(net_johnson):
  '''
  Ensure line segmentation process of Network initialization retains total line length
  within 0.1m
  '''
  net = net_johnson
  net.resolve_directions()
  assert round(
    net.lines.geometry.length.sum(), 1
  ) == round(
    net.segments.geometry.length.sum(), 1
  )


def test_points_in_graph_johnson(net_johnson):
  '''Ensure coordinates of various storm_points are present as nodes within the graph'''
  net = net_johnson
  net.resolve_directions()
  for idx in [20845, 244244, 21135, 244947, 244275]:
    x, y = network.get_point_coords(net.pts.loc[idx].geometry)
    assert net.G.has_node((x, y))


def test_resolve_direction_simple_johnson(net_johnson):
  '''
  Ensure the direction of a simple 3-node subgraph can be resolved such that the only
  edges present are in the correct direction of flow for that subgraph
  '''
  net = net_johnson
  net.resolve_directions()

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
  net.resolve_directions()
  
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
  net.resolve_directions()
  assert net.get_outlet(20847) == 21134


def test_resolve_catchment_johnson(net_johnson):
  '''
  Test that resolve_catchment_graph removes all bidirectional edges within the
  catchment, meaning the flow directions for the catchment subgraph have been fully
  resolved / have no ambiguity 
  '''
  catchment = gpd.read_file('tests/test_data/johnson_vt/initial_catchment.shp')

  net = net_johnson
  net.resolve_directions()
  
  # Check each point within the catchment to ensure it has no bidirectional edges
  catchment = catchment.to_crs(net.crs)
  catchment_pts = gpd.clip(net.pts, catchment)
  for pt in catchment_pts.itertuples('StormPoint'):
    x, y = network.get_point_coords(pt.geometry)
    predecessors = [u for u in net.G.predecessors((x, y))]
    successors = [v for v in net.G.successors((x, y))]
    # There should be no nodes that are both predecessors and successors
    assert len(set(predecessors).intersection(successors)) == 0


def test_consec_out_synth(net_synthetic):
  '''Test simple graph with two consecutive SOURCE/outfall points'''
  net = net_synthetic
  net.resolve_directions()
  first_out_pt_coords = tuple([net.pts.loc[14].geometry.x, net.pts.loc[14].geometry.y])
  successors = [v for v in net.G.successors(first_out_pt_coords)]
  assert len(successors) == 1

# TODO:
# Add tests for other direction resolution methods
# Add more tests for the synthetic testing data
