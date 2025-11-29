from collections import namedtuple
from typing import Optional
import warnings

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiPoint, Point


def get_point_coords(pt_geom, decimals: int = None) -> tuple:
    """
    Get and x, y coordinate tuple from a Point or MultiPoint shapely geometry

    Parameters
    ----------
    pt_geom : Point | MultiPoint
        shapely geometry object containing a point coordinate
    decimals : int (default None)
        Number of decimals to round coordinates to
    """
    if isinstance(pt_geom, Point):
        x = pt_geom.x
        y = pt_geom.y
    elif isinstance(pt_geom, MultiPoint):
        x = pt_geom.geoms[0].x
        y = pt_geom.geoms[0].y
        if len(pt_geom.geoms) > 1:
            warnings.warn(
                f"A point at coordinate ({x}, {y}) has MultiPoint geometry with "
                "multiple point coordinates, only returning the first"
            )
    else:
        raise ValueError(
            f"Failed to get coords for Point with geometry type: {type(pt_geom)}"
        )
    if decimals is not None:
        x = round(x, decimals)
        y = round(y, decimals)

    return x, y


class Network:
    """
    Parses through stormwater infrastructure point and line data to generate directional
    graphs represeting the connectivity of the infrastructure network.

    Attributes:
    -----------
    crs : pyproj.crs.crs.CRS
        The PyProj Coordinate Reference System of infrastructure data
    lines : gpd.GeoDataFrame
        All the stormwater infrastructure line features within the area of interest
    digraph : nx.DiGraph
        A list of all the graphs generated within the area of interest
    direction_resolved : bool
        Checks if Network is fully initialized and usable, equals True if directions of
        the edges in self.digraph have been resolved
    segments : gpd.GeoDataFrame
        All the stormwater infrastructure line geometry split into segments
    pts : gpd.GeoDataFrame
        All the stormwater infrastructure point features within the area of interest
    """

    def __init__(
        self,
        lines: gpd.GeoDataFrame,
        sink_pts: gpd.GeoDataFrame,
        source_pts: gpd.GeoDataFrame,
        coord_decimals: int = 3,
    ):
        """
        Parameters:
        ----------
        lines : gpd.GeoDataFrame
            All the stormwater infrastructure line features within the area of interest
        sink_pts : gpd.GeoDataFrame
            All the points that represent flow sinks in the infrastructure network,
            where flow enters the network, such as catchbasins
        source_pts : gpd.GeoDataFrame
            All the points that represent flow sources in the infrastructure network,
            where flow exits the network, such as outfalls
        coord_decimals : int (default 3)
            Decimal to round line coordinates too, prevents problems with improper snapping
        """

        # TODO: Identify private and public class attributes

        if sink_pts.crs != lines.crs or source_pts.crs != lines.crs:
            raise ValueError(
                "Coordinate reference systems of all point and line datasets must match"
            )
        self.crs = sink_pts.crs

        self.lines = lines

        # Explode all lines into 2-vertex segments while rounding coordinates
        self.digraph = nx.DiGraph()
        self.directions_resolved = False
        all_segments = {}
        for line in lines.itertuples():
            u_coords = line.geometry.coords[:-1]
            v_coords = line.geometry.coords[1:]
            # Round all coordinate values
            u_coords = [
                tuple([round(x, coord_decimals), round(y, coord_decimals)])
                for x, y in u_coords
            ]
            v_coords = [
                tuple([round(x, coord_decimals), round(y, coord_decimals)])
                for x, y in v_coords
            ]

            segments = list(map(LineString, zip(u_coords, v_coords)))
            all_segments[line.Index] = segments

        # Retain all segment data with the segment's source index stored in a column
        self.segments = gpd.GeoDataFrame()
        for src_index, segments in all_segments.items():
            segments = gpd.GeoDataFrame(geometry=gpd.GeoSeries(segments), crs=self.crs)
            segments["src_index"] = src_index
            self.segments = gpd.pd.concat([self.segments, segments], ignore_index=True)

        self.sink_pts = sink_pts
        self.source_pts = source_pts

        # Round all point coordinate values, also converting any MultiPoints to Points
        self.sink_pts["geometry"] = self.sink_pts["geometry"].apply(
            lambda geom: Point([get_point_coords(geom, coord_decimals)])
        )
        self.source_pts["geometry"] = self.source_pts["geometry"].apply(
            lambda geom: Point([get_point_coords(geom, coord_decimals)])
        )

    # TODO: Get rid of this namedtuple concept. Convert to StormPoint class if needed.
    # This just needs to be in it's init method somewhere
    def to_StormPoint(self, pt) -> "StormPoint":  # noqa
        """
        Converts point data from various types to a StormPoint namedtuple

        Parameters
        ----------
        pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Point data to convert to namedtuple

        Returns
        -------
        pt : StormPoint (namedtuple)
            Point data as a StormPoint namedtuple
        """
        if isinstance(pt, gpd.GeoDataFrame):
            if len(pt) > 1:
                warnings.warn(
                    "to_StormPoint() got multiple points, only keeping the first"
                )
            pt_iter = pt.itertuples(name="StormPoint")
            pt = next(pt_iter)
        elif isinstance(pt, pd.Series):
            # convert to StormPoint namedtuple
            field_names = self.sink_pts.columns.to_list()
            field_names.insert(0, "Index")
            pt = namedtuple("StormPoint", field_names)(pt.name, *pt)
        else:
            assert pt.__class__.__name__ == "StormPoint", (
                f"Expected pt to be a "
                "gpd.GeoDataFrame, pd.Series, or a StormPoint namedtuple, but got a "
                f"{pt.__class__.__name__}"
            )
        return pt

    def has_StormPoint(self, pt) -> bool:
        """
        Check if self.digraph contains a given StormPoint

        Parameters
        ----------
        pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Point whose coordinate pair will searched for in self.digraph

        Returns
        -------
        has_node : bool
            True if the pt's coordinate pair is present as a node in self.digraph
        """
        pt = self.to_StormPoint(pt)
        pt_x = pt.geometry.x
        pt_y = pt.geometry.y
        return self.digraph.has_node((pt_x, pt_y))

    def resolve_upstream(self, source_pt) -> None:
        """
        Initializiton function for traverse_upstream, prepares arguments for depth-first
        search

        Parameters
        ----------
        source_pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Infrastructure point which is a flow source/discharge point (IS_SOURCE=True)
        """
        source_pt = self.to_StormPoint(source_pt)

        v_x = source_pt.geometry.x
        v_y = source_pt.geometry.y

        visited = set()
        self.traverse_upstream((v_x, v_y), visited)

    def traverse_upstream(self, coords: tuple, visited: set) -> None:
        """
        Revise direction of edges via recursive depth-first search, starting from an
        outlet then traverse the graph "upstream". Visits every node that's connected to
        the initial source node.

        Parameters
        ----------
        coords : tuple
            Tuple of current (x, y) float coordinates. These coordinates are the
            name/index of the nodes in self.digraph
        visited : set
            Used to record which coordinates have already been visited in this search
        """
        v = coords
        visited.add(v)
        for u in self.digraph.predecessors(v):
            if u not in visited:
                # Only retain edge from u -> v
                if self.digraph.has_edge(v, u):
                    assert self.digraph.has_edge(u, v)
                    self.digraph.remove_edge(v, u)
                self.traverse_upstream(u, visited)

    def add_edges(self, direction: str, verbose: bool = False) -> None:
        """
        Utilize user storm line data to add edges (and their nodes) to self.digraph in
        one or both directions

        Parameters
        ----------
        direction : str
            Direction to add edges in, based on the order of verticies in the user's
            stormwater infrastructure line data (self.lines & self.segments). Can be
            'both', 'original', or 'reverse'
        verbose : bool
            Set to True to print direction resolution/edge addition results to console
        """
        if verbose:
            print("Adding edges...")

        if direction == "both" or direction == "original":
            self.segments["geometry"].apply(
                lambda seg: self.digraph.add_edge(seg.coords[0], seg.coords[1])
            )
        elif direction == "both" or direction == "reverse":
            self.segments["geometry"].apply(
                lambda seg: self.digraph.add_edge(seg.coords[1], seg.coords[0])
            )
        else:
            raise ValueError(
                f'direction "{direction}" is invalid, must be "both", "original", or '
                '"reverse"'
            )

        if verbose:
            if direction == "original" or direction == "reverse":
                print(f"Succesfully added {self.digraph.number_of_edges()} edges")

    def resolve_from_sources(self, verbose: bool = False) -> None:
        """
        Resolve directions of all edges within the graph by traversing subgraphs
        upstream from each flow source

        Parameters
        ----------
        verbose : bool (default False)
            Set to True to print direction resolution results to console
        """
        self.add_edges(direction="both", verbose=verbose)

        missing_pts = []

        for pt in self.source_pts.itertuples(name="StormPoint"):
            if not self.has_StormPoint(pt):
                missing_pts.append(pt.Index)
                continue
            self.resolve_upstream(pt)

        if verbose:
            if len(missing_pts) > 0:
                print(
                    "The following flow source points were not present in the graph, "
                    "ensure that they are properly snapped to a line vertex: ",
                    missing_pts,
                )

            n_bidirectional = 0
            n_unidirectional = 0
            for u, v in self.digraph.edges():
                if self.digraph.has_edge(v, u):
                    n_bidirectional += 1
                else:
                    n_unidirectional += 1
            print(f"Succesfully resolved direction for {n_unidirectional} edges")
            if n_bidirectional > 0:
                print(f"Failed to resolve direction for {n_bidirectional / 2} edges")

    def resolve_directions(
        self, method: str = "from_sources", verbose: bool = False
    ) -> None:
        """
        Attempt to resolve directions for all edges within the graph

        Parameters
        ----------
        method : str (default 'from_sources')
            Method to resolve edge directions for self.digraph, can be one of the following:
            - 'from_sources': Traverses upstream from each outlet point (where
                self.pts['IS_SOURCE'] == True) to define edge directions to point to
                outlets
            - 'vertex_order': Defines edge directions using the order of verticies in
                self.lines
            - 'vertex_order_r': Defines edge directions using reverse order of verticies
                in self.lines
        verbose : bool (default False)
            Set to True to print direction resolution results to console
        """
        if method == "from_sources":
            self.resolve_from_sources(verbose=verbose)
        elif method == "vertex_order":
            self.add_edges(direction="original", verbose=verbose)
        elif method == "vertex_order_r":
            self.add_edges(direction="reverse", verbose=verbose)
        else:
            raise ValueError(
                f'Method "{method}" is not a valid edge resolution method, must be '
                '"from_sources", "vertex_order", or "vertex_order_r".'
            )

        self.directions_resolved = True

    def get_outlet(self, sink_pt_idx: int) -> Optional[int]:
        """
        Get Index of the outlet for a given storm_pt whose coordinates exist in the
        graph

        Parameters
        ----------
        sink_pt_idx : int
            Index of point, note that OBJECTID is the default index column
        """
        if not self.directions_resolved:
            raise ValueError("Cannot get outlet until graph directions are resolved")

        pt_x, pt_y = get_point_coords(self.sink_pts.loc[sink_pt_idx].geometry)
        if (pt_x, pt_y) not in self.digraph:
            warnings.warn(
                f"The point with index {sink_pt_idx} does not have its coordinates as "
                "a node in the graph"
            )
            return None

        sub_graph = nx.dfs_tree(self.digraph, (pt_x, pt_y))
        outlet_coords = [coords for coords, deg in sub_graph.out_degree() if deg == 0]
        if len(outlet_coords) == 0:
            raise ValueError(
                f"Subgraph of point with index {sink_pt_idx} has no outlet"
            )
        elif len(outlet_coords) > 1:
            warnings.warn(
                f"Multiple outlet coordinates found for point with index {sink_pt_idx}, "
                "only returning the first"
            )

        outlet_x, outlet_y = outlet_coords[0]
        outlet_pts = self.source_pts.cx[outlet_x, outlet_y]  # gpd.GeoDataFrame
        if len(outlet_pts) == 0:
            return None
        elif len(outlet_pts) > 1:
            warnings.warn(
                f"Multiple outlet coordinates found for point with index {sink_pt_idx}, "
                "only returning the first"
            )

        return outlet_pts.iloc[0].name

    def get_outlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Get GeoDataFrame of all the infrastructure points within the catchment that
        bring flow out of the current catchment. The catchments for these points will
        need to be removed from current catchment.

        Parameters
        ----------
        catchment : gpd.GeoDataFrame
            GeoDataFrame containing the current catchment polygon

        Returns
        -------
        outlet_pts : gpd.GeoDataFrame
            GeoDataFrame containing all the points that bring flow out of the current
            catchment
        """
        if catchment.crs != self.crs:
            catchment = catchment.to_crs(crs=self.crs)

        catchment_sink_pts = gpd.clip(self.sink_pts, catchment)
        catchment_source_pts = gpd.clip(self.source_pts, catchment)

        sink_idxs_to_remove = []
        sink_pt_idxs = catchment_sink_pts.index.to_list()
        for idx in sink_pt_idxs:
            outlet_idx = self.get_outlet(idx)
            if outlet_idx is not None and outlet_idx not in catchment_source_pts.index:
                sink_idxs_to_remove.append(idx)

        return self.sink_pts.loc[sink_idxs_to_remove]

    def get_inlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Get GeoDataFrame of all the infrastructure points outside the catchment that
        bring flow into the catchment.

        Parameters
        ----------
        catchment : gpd.GeoDataFrame
            GeoDataFrame containing the current catchment polygon

        Returns
        -------
        inlet_pts : gpd.GeoDataFrame
            GeoDataFrame containing all the points outside the catchment that bring flow
            into the catchment
        """
        if not self.directions_resolved:
            raise ValueError(
                "Cannot get inlet points until graph directions are resolved"
            )

        if catchment.crs != self.crs:
            catchment = catchment.to_crs(crs=self.crs)

        catchment_source_pts = gpd.clip(self.source_pts, catchment)
        source_pt_geoms = catchment_source_pts.geometry.tolist()
        source_pt_coords = [get_point_coords(geom) for geom in source_pt_geoms]

        contrib_sink_idxs = set()
        for coords in source_pt_coords:
            tree = nx.bfs_tree(self.digraph, coords, reverse=True)

            for node in tree.nodes():
                if catchment.contains(Point(node)).any():
                    continue

                # Check for any sinks at these coordinates
                sink_pt = self.sink_pts.cx[node[0], node[1]]
                if not sink_pt.empty:
                    sink_pt = self.to_StormPoint(sink_pt)
                    contrib_sink_idxs.add(sink_pt.Index)

        return self.sink_pts.loc[list(contrib_sink_idxs)]

    def draw(
        self, extent: gpd.GeoDataFrame = None, ax=None, add_basemap: bool = False
    ) -> "plt.axes":  # noqa
        """
        Draw the Graph using the geographic coordinates of each node

        Parameters
        ----------
        extent : gpd.GeoDataFrame (default None)
            GeoDataFrame whose extent will be used to trim the infrastructure data

        ax : plt.axes | None (default None)
            Matplotlib axes object to utilize for plot

        add_basemap : bool (deafult False)
            Option to add a contextily basemap to the plot
        """
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection

        if add_basemap:
            import contextily as cx

        if ax is None:
            ax = plt.gca()
            ax.axis("equal")

        # Extent geometry
        if extent is not None:
            if extent.crs != self.crs:
                extent = extent.to_crs(self.crs)
            envelope = extent["geometry"].envelope.iloc[0]

        bidirectional_edges = []
        directional_edges = []
        for edge in self.digraph.edges():
            if extent is not None:
                # Exclude edges with no verticies within extent
                if not envelope.contains(
                    Point(edge[0][0], edge[0][1])
                ) and not envelope.contains(Point(edge[1][0], edge[1][1])):
                    continue
            if self.digraph.has_edge(edge[1], edge[0]):
                bidirectional_edges.append(edge)
            else:
                directional_edges.append(edge)

        # Plot directional edges as arrows
        for edge in directional_edges:
            u_x, u_y = edge[0]
            v_x, v_y = edge[1]
            ax.arrow(
                u_x,
                u_y,
                v_x - u_x,
                v_y - u_y,
                shape="left",
                width=0.1,
                head_width=2,
                length_includes_head=True,
                ec="darkblue",
                fc="cyan",
                zorder=1,
            )

        # Plot bidirectional edges as segments
        lc = LineCollection([edge for edge in bidirectional_edges], color="darkblue")
        ax.add_collection(lc)

        pts = self.pts.copy(deep=True)
        if extent is not None:
            pts = gpd.clip(pts, extent["geometry"].envelope)

        # Plot points
        sink_pts = pts[pts["IS_SINK"] == True]  # noqa
        source_pts = pts[pts["IS_SOURCE"] == True]  # noqa
        other_pts = pts[(pts["IS_SINK"] == False) & (pts["IS_SOURCE"] == False)]  # noqa
        sink_pts.plot(
            ax=ax, color="white", marker="s", edgecolor="black", markersize=10, zorder=2
        )
        source_pts.plot(
            ax=ax, color="white", marker="o", edgecolor="black", markersize=10, zorder=2
        )
        other_pts.plot(
            ax=ax, color="gray", marker="o", edgecolor="black", markersize=10, zorder=2
        )

        if add_basemap:
            try:
                cx.add_basemap(
                    ax,
                    source=cx.providers.Esri.WorldImagery,
                    crs=self.crs.to_string(),
                    alpha=0.7,
                )
            except Exception as e:
                warnings.warn(
                    "The following exception was raised while trying to add the"
                    "contextily basemap:",
                    e,
                )

        return ax
