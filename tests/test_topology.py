from shapely.geometry import MultiLineString, Point

from stormcatchments.utils import topology


def test_find_multi_outlet(net_synthetic):
    net = net_synthetic
    net.resolve_directions()

    multi_out_geom = topology.find_multi_outlet(net).geometry

    pt_not_in_multiout = Point(-7812989.354, 5166001.217)
    pt_in_multiout = Point(-7812971.672, 5166006.809)

    assert not multi_out_geom.intersects(pt_not_in_multiout).any()
    assert multi_out_geom.intersects(pt_in_multiout).any()


def test_get_all_floating_points(net_synthetic):
    net = net_synthetic
    floating_sink_pts, floating_source_pts = topology.get_all_floating_points(net)
    assert [18] == floating_sink_pts.index.values.tolist()
    assert [21] == floating_source_pts.index.values.tolist()


def test_snap_all_points(net_synthetic):
    net = net_synthetic
    net_snapped = topology.snap_all_points(net, 10.0)

    # Two previously unsnapped points
    pt_18 = net_snapped.sink_pts.loc[18].geometry
    pt_21 = net_snapped.source_pts.loc[21].geometry

    net_geom = MultiLineString([line for line in net.segments["geometry"]])

    assert net_geom.intersects(pt_18)
    assert net_geom.intersects(pt_21)


def test_snap_tolerance(net_synthetic):
    net = net_synthetic
    net_snapped = topology.snap_all_points(net, 3.0)

    # Two previously unsnapped points
    pt_18 = net_snapped.sink_pts.loc[18].geometry  # >3.0m from nearest vertex
    pt_21 = net_snapped.source_pts.loc[21].geometry  # <3.0m from nearest vertex
    net_geom = MultiLineString([line for line in net.segments["geometry"]])

    assert not net_geom.intersects(pt_18)
    assert net_geom.intersects(pt_21)
