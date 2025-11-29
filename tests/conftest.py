import geopandas as gpd
import pytest

from stormcatchments import delineate, network
from stormcatchments.utils import terrain


SINK_TYPES_VT = [
    2,  # Catchbasin
    8,  # Culvert inlet
]

SOURCE_TYPES_VT = [
    5,  # Outfall
    9,  # Culvert outlet
]


@pytest.fixture(scope="function")
def net_johnson():
    storm_lines = gpd.read_file("tests/test_data/johnson_vt/storm_lines.shp")
    storm_lines.set_index("OBJECTID", inplace=True)
    storm_pts = gpd.read_file("tests/test_data/johnson_vt/storm_pts.shp")
    storm_pts.set_index("OBJECTID", inplace=True)
    sink_pts = storm_pts[storm_pts["Type"].isin(SINK_TYPES_VT)]
    source_pts = storm_pts[storm_pts["Type"].isin(SOURCE_TYPES_VT)]

    net = network.Network(
        storm_lines,
        sink_pts,
        source_pts,
    )
    return net


@pytest.fixture
def delineate_johnson(net_johnson):
    net_johnson.resolve_directions()

    # pysheds DEM loading, conditioning, and preprocessing
    grid, fdir, acc = terrain.preprocess_dem("tests/test_data/johnson_vt/dem.tif")

    return delineate.Delineate(net_johnson, grid, fdir, acc, 6589)


@pytest.fixture
def net_synthetic():
    storm_lines = gpd.read_file("tests/test_data/synthetic/lines.shp")

    storm_pts = gpd.read_file("tests/test_data/synthetic/pts.shp")
    sink_pts = storm_pts[storm_pts["IS_SINK"] == 1]
    source_pts = storm_pts[storm_pts["IS_SOURCE"] == 1]
    sink_pts.set_index("id", inplace=True)
    source_pts.set_index("id", inplace=True)

    net = network.Network(storm_lines, sink_pts, source_pts)
    return net
