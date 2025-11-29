"""topology utils

Various utility functions for validating/cleaning the topology of vector networks
"""

from copy import deepcopy
from typing import Literal

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiLineString, Point

from stormcatchments.network import Network


def _get_floating_points(
    net: Network, pt_type: Literal["sink", "source"]
) -> gpd.GeoDataFrame:
    floating_pts = []
    if pt_type == "sink":
        pts_to_check = net.sink_pts
    elif pt_type == "source":
        pts_to_check = net.source_pts
    else:
        raise ValueError("pt_type must be either 'sink' or 'source'")

    for pt in pts_to_check.itertuples():
        # Get all segments that pt touches
        touch_segs = net.segments[net.segments.geometry.touches(pt.geometry)]

        # Check for case where pt doesn't touch any segment at all
        if len(touch_segs) == 0:
            floating_pts.append(pt)
            continue

        # Check for case where pt touches segments but not at a vertex
        seg_coords = set()
        for line in touch_segs.geometry:
            for coord in line.coords:
                seg_coords.add(coord)

        if (pt.geometry.x, pt.geometry.y) not in seg_coords:
            floating_pts.append(pt)

    return gpd.GeoDataFrame(floating_pts, crs=net.crs).set_index("Index")


def get_all_floating_points(net: Network) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Find and return any points in a Network that are not snapped to a line vertex. These
    floating points cannot be integrated into networking functionality unless they are
    snapped to a line vertex.

    Parameters
    ----------
    net : Network
      A stormcatchments Network object whose point data will be inspected for floating
      points

    Returns
    -------
    floating_sink_pts : gpd.GeoDataFrame
      A GeoDataFrame of any floating sink points in the Network
    floating_source_pts : gpd.GeoDataFrame
      A GeoDataFrame of any floating source points in the Network
    """
    # floating_sink_pts = []
    # floating_source_pts = []
    # # all_net_pts = pd.concat([net.sink_pts, net.source_pts])
    # for pt in net.sink_pts.itertuples():
    #     # Get all segments that pt touches, could be on a vertex or between verticies
    #     touch_segs = net.segments[net.segments.geometry.touches(pt.geometry)]

    #     if len(touch_segs) == 0:
    #         floating_sink_pts.append(pt)
    #         continue

    #     # Collect segment coordinates as (x, y) tuples
    #     seg_coords = set()
    #     for line in touch_segs.geometry:
    #         for coord in line.coords:
    #             seg_coords.add(coord)

    #     if (pt.geometry.x, pt.geometry.y) not in seg_coords:
    #         floating_sink_pts.append(pt)

    # return gpd.GeoDataFrame(floating_pts, crs=net.crs).set_index("Index")
    return (
        _get_floating_points(net, "sink"),
        _get_floating_points(net, "source"),
    )


def _snap_points(
    net: Network,
    pt_type: Literal["sink", "source"],
    floating_pts: gpd.GeoDataFrame,
    tolerance: float,
) -> Network:
    net_snapped = deepcopy(net)
    for pt in floating_pts.itertuples():
        nearby = net.segments.cx[
            pt.geometry.x - tolerance : pt.geometry.x + tolerance,
            pt.geometry.y - tolerance : pt.geometry.y + tolerance,
        ]

        closest_xy = None
        closest_dist = tolerance**2
        for line in nearby.geometry:
            for coord in line.coords:
                dist = pt.geometry.distance(Point(coord))
                if dist < closest_dist:
                    closest_dist = dist
                    closest_xy = coord

        if closest_dist <= tolerance:
            # Replace point in network
            if pt_type == "sink":
                net_snapped.sink_pts.at[pt.Index, "geometry"] = Point(closest_xy)
            elif pt_type == "source":
                net_snapped.source_pts.at[pt.Index, "geometry"] = Point(closest_xy)
            else:
                raise ValueError("pt_type must be either 'sink' or 'source'")

    return net_snapped


def snap_all_points(net: Network, tolerance: float) -> Network:
    """
    Create a copy of a supplied Network which snaps any points in Network to the
    closest line vertex within a snapping tolerance

    Parameters
    ----------
    net : Network
      A stormcatchments Network object which may contain floating points

    tolerance : float
      The maximum search distance to find the nearest vertex

    Returns
    -------
    net_snapped : Network
      A stormcatchments Network object with snapping applied to its point data
    """
    # Snap all floating (un-snapped) points to the nearest line vertex
    floating_sink_pts, floating_source_pts = get_all_floating_points(net)

    net_sink_pts_snapped = _snap_points(net, "sink", floating_sink_pts, tolerance)
    net_all_pts_snapped = _snap_points(
        net_sink_pts_snapped, "source", floating_source_pts, tolerance
    )

    # net_snapped = deepcopy(net)
    # for pt in floating_sink_pts.itertuples():
    #     nearby = net.segments.cx[
    #         pt.geometry.x - tolerance : pt.geometry.x + tolerance,
    #         pt.geometry.y - tolerance : pt.geometry.y + tolerance,
    #     ]

    #     closest_xy = None
    #     closest_dist = tolerance**2
    #     for line in nearby.geometry:
    #         for coord in line.coords:
    #             dist = pt.geometry.distance(Point(coord))
    #             if dist < closest_dist:
    #                 closest_dist = dist
    #                 closest_xy = coord

    #     if closest_dist <= tolerance:
    #         net_snapped.pts.at[pt.Index, "geometry"] = Point(closest_xy)

    return net_all_pts_snapped


def find_multi_outlet(net: Network) -> gpd.GeoDataFrame:
    """
    Find all subnetworks within greater Network that have more than one flow source/outlet

    Parameters
    ----------
    net : Network
      A stormcatchments Network with resolved directions

    Returns
    -------
    mutli_out : gpd.GeoDataFrame
      A GeoDataFrame containing one MultiLineString features for each connected subgraph
      with multiple outlets/flow sources. If no multi-outlet subgraphs are found an empty
      GeoDataFrame is returned
    """
    if not net.directions_resolved:
        raise ValueError(
            "Network directions must be resolved prior to searching for mutli-outlet "
            "componenets"
        )

    multi_out_geoms = []

    for c in nx.weakly_connected_components(net.digraph):
        outlets = set()
        # Count flow sources (outlets) in current weakly connected component
        for node in c:
            pt = net.source_pts.cx[node[0] : node[0], node[1] : node[1]]
            if not pt.empty:
                outlets.add(node)

        if len(outlets) > 1:
            sub_g = nx.subgraph(net.digraph, c)
            sub_g_geom = MultiLineString([LineString(e) for e in sub_g.edges()])
            multi_out_geoms.append(sub_g_geom)

    return gpd.GeoDataFrame(geometry=gpd.GeoSeries(multi_out_geoms), crs=net.crs)
