import geopandas as gpd
import pandas as pd

from stormcatchments import network


def test_non_empty_graph_johnson(net_johnson):
    """Ensure Network initialization generates non-empty graph"""
    net = net_johnson
    net.resolve_directions()
    assert not net.segments.empty
    assert net.digraph.number_of_nodes() > 0


def test_line_segmentation_johnson(net_johnson):
    """
    Ensure line segmentation process of Network initialization retains total line length
    within 0.1m
    """
    net = net_johnson
    net.resolve_directions()
    assert round(net.lines.geometry.length.sum(), 1) == round(
        net.segments.geometry.length.sum(), 1
    )


def test_points_in_graph_johnson(net_johnson):
    """Ensure coordinates of various storm_points are present as nodes within the graph"""
    net = net_johnson
    net.resolve_directions()

    # Known sinks
    for idx in [20845, 21135, 244275]:
        x, y = network.get_point_coords(net.sink_pts.loc[idx].geometry)
        assert net.digraph.has_node((x, y))

    # Known sources
    for idx in [244244, 244947]:
        x, y = network.get_point_coords(net.source_pts.loc[idx].geometry)
        assert net.digraph.has_node((x, y))


def test_resolve_direction_simple_johnson(net_johnson):
    """Ensure the direction of a simple 3-node subgraph can be resolved such that the only
    edges present are in the correct direction of flow for that subgraph
    """
    net = net_johnson
    net.resolve_directions()

    # Points known to be in the graph. Neither sinks nor sources
    u1_x, u1_y = (484628.134, 237228.753)
    v1_x, v1_y = (484624.033, 237226.107)

    u2_x = v1_x
    u2_y = v1_y
    v2_x, v2_y = network.get_point_coords(net.source_pts.loc[244244].geometry)

    assert net.digraph.has_edge((u1_x, u1_y), (v1_x, v1_y))
    assert not net.digraph.has_edge((v1_x, v1_y), (u1_x, u1_y))

    assert net.digraph.has_edge((u2_x, u2_y), (v2_x, v2_y))
    assert not net.digraph.has_edge((v2_x, v2_y), (u2_x, u2_y))


def test_resolve_direction_complex_johnson(net_johnson):
    """Ensure the direction of a larger subgraph with multiple branches can be resolved
    such that the only edges present are in the correct direction of flow for that
    subgraph
    """
    net = net_johnson
    net.resolve_directions()

    # Interconnected sinks (catchbasins)
    sink_edges = {20846: 20845, 20847: 20846, 21135: 20845}
    for u, v in sink_edges.items():
        u_x, u_y = network.get_point_coords(net.sink_pts.loc[u].geometry)
        v_x, v_y = network.get_point_coords(net.sink_pts.loc[v].geometry)
        # Edge is present in correct direction of flow
        assert net.digraph.has_edge((u_x, u_y), (v_x, v_y))
        # Edge is not present in reverse of flow direction
        assert not net.digraph.has_edge((v_x, v_y), (u_x, u_y))

    # Check source/outfall edge as well
    u_x, u_y = network.get_point_coords(net.sink_pts.loc[20845].geometry)
    v_x, v_y = network.get_point_coords(net.source_pts.loc[21134].geometry)
    assert net.digraph.has_edge((u_x, u_y), (v_x, v_y))
    assert not net.digraph.has_edge((v_x, v_y), (u_x, u_y))


def test_get_outlet_johnson(net_johnson):
    """After resolving direction for a SINK point, test that it's outlet is properly
    identified
    """
    net = net_johnson
    net.resolve_directions()
    assert net.get_outlet(20847) == 21134


def test_resolve_catchment_johnson(net_johnson):
    """Test that resolve_catchment_graph removes all bidirectional edges within the
    catchment, meaning the flow directions for the catchment subgraph have been fully
    resolved / have no ambiguity
    """
    catchment = gpd.read_file("tests/test_data/johnson_vt/initial_catchment.shp")

    net = net_johnson
    net.resolve_directions()

    # Check each point within the catchment to ensure it has no bidirectional edges
    catchment = catchment.to_crs(net.crs)
    catchment_pts = pd.concat(
        [gpd.clip(net.sink_pts, catchment), gpd.clip(net.source_pts, catchment)]
    )
    for pt in catchment_pts.itertuples("StormPoint"):
        x, y = network.get_point_coords(pt.geometry)
        predecessors = [u for u in net.digraph.predecessors((x, y))]
        successors = [v for v in net.digraph.successors((x, y))]
        # There should be no nodes that are both predecessors and successors
        assert len(set(predecessors).intersection(successors)) == 0


def test_consec_out_synth(net_synthetic):
    """Test simple graph with two consecutive SOURCE/outfall points"""
    net = net_synthetic
    net.resolve_directions()
    first_out_pt_coords = tuple(
        [net.source_pts.loc[14].geometry.x, net.source_pts.loc[14].geometry.y]
    )
    successors = [v for v in net.digraph.successors(first_out_pt_coords)]
    assert len(successors) == 1


# TODO:
# Add tests for other direction resolution methods
# Add more tests for the synthetic testing data
