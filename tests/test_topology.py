import geopandas as gpd
from shapely.geometry import MultiLineString
import pytest

from stormcatchments import network, topology
from stormcatchments.constants import SINK_TYPES_VT, SOURCE_TYPES_VT

@pytest.fixture
def net_synth():
  # Intialize network but leave directions unresolved
  storm_lines = gpd.read_file('tests/test_data/synthetic/lines.shp')
  storm_lines.set_index('id', inplace=True)
  storm_pts = gpd.read_file('tests/test_data/synthetic/pts.shp')
  storm_pts.set_index('id', inplace=True)
  storm_pts['IS_SOURCE'] = storm_pts['IS_SOURCE'].astype(bool)
  storm_pts['IS_SINK'] = storm_pts['IS_SINK'].astype(bool)

  net = network.Network(
    storm_lines,
    storm_pts
  )
  return net


def test_find_multi_outlet(net_synth):
  net = net_synth
  net.resolve_directions()

  multi_out_geom = topology.find_multi_outlet(net).geometry

  pt_3 = net.pts.loc[3].geometry
  pt_12 = net.pts.loc[12].geometry

  assert not multi_out_geom.intersects(pt_3).any()
  assert multi_out_geom.intersects(pt_12).any()


def test_find_floating_points(net_synth):
  net = net_synth
  floating = topology.find_floating_points(net)
  assert [18, 21] == floating.index.values.tolist()


def test_snap_points(net_synth):
  net = net_synth
  net_snapped = topology.snap_points(net, 10.0)
  
  # Two previously unsnapped points
  pt_18 = net_snapped.pts.loc[18].geometry
  pt_21 = net_snapped.pts.loc[21].geometry

  net_geom = MultiLineString([l for l in net.segments['geometry']])

  assert net_geom.intersects(pt_18)
  assert net_geom.intersects(pt_21)


def test_snap_tolerance(net_synth):
  net = net_synth
  net_snapped = topology.snap_points(net, 3.0)

  # Two previously unsnapped points
  pt_18 = net_snapped.pts.loc[18].geometry # >3.0m from nearest vertex
  pt_21 = net_snapped.pts.loc[21].geometry # <3.0m from nearest vertex

  net_geom = MultiLineString([l for l in net.segments['geometry']])

  assert not net_geom.intersects(pt_18)
  assert net_geom.intersects(pt_21)
