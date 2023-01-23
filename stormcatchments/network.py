from collections import namedtuple
from typing import Optional
import warnings

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiPoint, Point


def get_point_coords(pt_geom, decimals: int=None) -> tuple:
    '''
    Get and x, y coordinate tuple from a Point or MultiPoint shapely geometry

    Parameters
    ----------
    pt_geom : Point | MultiPoint
        shapely geometry object containing a point coordinate
    decimals : int (default None)
        Number of decimals to round coordinates to
    '''
    if isinstance(pt_geom, Point):
        x = pt_geom.x
        y = pt_geom.y
    elif isinstance(pt_geom, MultiPoint):
        x = pt_geom.geoms[0].x
        y = pt_geom.geoms[0].y
        if len(pt_geom.geoms) > 1:
            warnings.warn(
                f'A point at coordinate ({x}, {y}) has MultiPoint geometry with '
                'multiple point coordinates, only returning the first'
        )
    else:
        raise ValueError(
            f'Failed to get coords for Point with geometry type: {type(pt_geom)}'
        )
    if decimals is not None:
        x = round(x, decimals)
        y = round(y, decimals)
    
    return x, y


class Network:
    '''
    Parses through stormwater infrastructure point and line data to generate directional
    graphs represeting the connectivity of the infrastructure network.
    
    Attributes:
    -----------
    crs : pyproj.crs.crs.CRS
        The PyProj Coordinate Reference System of infrastructure data
    lines : gpd.GeoDataFrame
        All the stormwater infrastructure line features within the area of interest
    G : nx.DiGraph
        A list of all the graphs generated within the area of interest
    direction_resolved : bool
        Checks if Network is fully initialized and usable, equals True if directions of
        the edges in self.G have been resolved
    segments : gpd.GeoDataFrame
        All the stormwater infrastructure line geometry split into segments
    pts : gpd.GeoDataFrame
        All the stormwater infrastructure point features within the area of interest
    '''
    def __init__(
        self,
        storm_lines: gpd.GeoDataFrame,
        storm_pts: gpd.GeoDataFrame,
        coord_decimals: int=3,
        type_column: Optional[str]=None,
        sink_types: Optional[list]=None,
        source_types: Optional[list]=None,
    ):
        '''
        Parameters:
        ----------
        storm_lines : gpd.GeoDataFrame
            All the stormwater infrastructure line features within the area of interest
        storm_pts : gpd.GeoDataFrame
            All the stormwater infrastructure points features within the area of interest
        coord_decimals : int (default 3)
            Decimal to round line coordinates too, prevents problems with improper snapping
        type_column : str | None (default None)
            Column in storm_pts GeoDataFrame that represents the type of each point
            (e.g., catchbasins, outfalls, culverts), set to None if IS_SOURCE and
            IS_SINK are preconfigured in the storm_pts GeoDataFrame
        sink_types : list (default None)
            List of type values that correspond to flow sinks, where flow enters at
            these points, such as a catchbasin
        source_types : list (default None)
            List of type values that correspond to flow sources, where flow exits at
            these points, such as an outfall 
        '''
        if storm_pts.crs != storm_lines.crs:
            raise ValueError(
                'Coordinate reference systems of point and line datasets must match'
            )
        self.crs = storm_pts.crs

        self.lines = storm_lines
        # Explode all lines into 2-vertex segments while rounding coordinates
        self.G = nx.DiGraph()
        self.directions_resolved = False
        all_segments = {}
        for line in storm_lines.itertuples(name='StormLine'):
            u_coords = line.geometry.coords[:-1]
            v_coords = line.geometry.coords[1:]
            # Round all coordinate values
            u_coords = [
                tuple(
                    [round(x, coord_decimals), round(y, coord_decimals)]
                ) for x, y in u_coords
            ]
            v_coords = [
                tuple(
                    [round(x, coord_decimals), round(y, coord_decimals)]
                ) for x, y in v_coords
            ]

            segments = list(map(LineString, zip(u_coords, v_coords)))
            all_segments[line.Index] = segments

        # Retain all segment data with the segment's source index stored in a column
        self.segments = gpd.GeoDataFrame()
        for src_index, segments in all_segments.items():
            segments = gpd.GeoDataFrame(geometry=gpd.GeoSeries(segments), crs=self.crs)
            segments['src_index'] = src_index
            self.segments = gpd.pd.concat([self.segments, segments], ignore_index=True)

        self.pts = storm_pts
        # Deal with mapping of IS_SOURCE and IS_SINK in point data
        if type_column is None:
            # User supplied SINK and SOURCE data
            if 'IS_SINK' not in self.pts.columns:
                raise ValueError(
                    'Column "IS_SINK" not present in point data. Supply a bool column '
                    'named "IS_SINK" or supply a type_column and list of sink_types to '
                    'map onto "IS_SINK"'
                )
            elif self.pts.dtypes['IS_SINK'] != bool:
                raise ValueError('Column "IS_SINK" must be bool type')
            elif 'IS_SOURCE' not in self.pts.columns:
                raise ValueError(
                    'Column "IS_SOURCE" not present in point data. Supply a bool '
                    'column named "IS_SOURCE" or supply a type_column and list of '
                    'source_types to map onto "IS_SOURCE"'                    
                )
            elif self.pts.dtypes['IS_SOURCE'] != bool:
                raise ValueError('Column "IS_SOURCE" must be bool type')
        else:
            # Need to map SINK and SOURCE data
            if type_column not in self.pts.columns:
                raise ValueError(
                    f'type_column "{type_column}" not present in point data'
                )
            elif sink_types is None:
                raise ValueError(
                    'To map data to IS_SINK a sink_types argument is required'
                )
            elif source_types is None:
                raise ValueError(
                    'To map data to IS_SOURCE a source_type argument is required'
                )

            self.pts['IS_SINK'] = self.pts[type_column].apply(
                lambda x: True if x in sink_types else False
            )
            self.pts['IS_SOURCE'] = self.pts[type_column].apply(
                lambda x: True if x in source_types else False
            )

        # Round all point coordinate values, also converting any MultiPoints to Points
        self.pts['geometry'] = self.pts['geometry'].apply(
            lambda geom: Point([get_point_coords(geom, coord_decimals)])
        )


    def to_StormPoint(self, pt) -> 'StormPoint':
        '''
        Converts point data from various types to a StormPoint namedtuple

        Parameters
        ----------
        pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Point data to convert to namedtuple
        
        Returns
        -------
        pt : StormPoint (namedtuple)
            Point data as a StormPoint namedtuple
        '''
        if isinstance(pt, gpd.GeoDataFrame):
            if len(pt) > 1:
                warnings.warn(
                    'to_StormPoint() got multiple points, only keeping the first'
                )
            pt_iter = pt.itertuples(name='StormPoint')
            pt = next(pt_iter)
        elif isinstance(pt, pd.Series):
            # convert to StormPoint namedtuple
            field_names = self.pts.columns.to_list()
            field_names.insert(0, 'Index')
            pt = namedtuple('StormPoint', field_names)(pt.name, *pt)
        else:
            assert pt.__class__.__name__ == 'StormPoint', f'Expected pt to be a ' \
                'gpd.GeoDataFrame, pd.Series, or a StormPoint namedtuple, but got a ' \
                f'{pt.__class__.__name__}'
        return pt


    def has_StormPoint(self, pt) -> bool:
        '''
        Check if self.G contains a given StormPoint

        Parameters
        ----------
        pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Point whose cooridnate pair will searched for in self.G

        Returns
        -------
        has_node : bool
            True if the pt's coordinate pair is present as a node in self.G
        '''
        pt = self.to_StormPoint(pt)
        pt_x = pt.geometry.x
        pt_y = pt.geometry.y
        return self.G.has_node((pt_x, pt_y))


    def resolve_upstream(self, source_pt) -> None:
        '''
        Initializiton function for traverse_upstream, prepares arguments for depth-first
        search

        Parameters
        ----------
        source_pt : gpd.GeoDataFrame | pd.Series | StormPoint (namedtuple)
            Infrastructure point which is a flow source/discharge point (IS_SOURCE=True)
        '''
        source_pt = self.to_StormPoint(source_pt)
        if not source_pt.IS_SOURCE:
            raise ValueError(
                f'Cannot resolve direction from point with Index {source_pt.Index} as '
                f'it is not marked as a flow source, see "IS_SOURCE": {source_pt}'
            )
        v_x = source_pt.geometry.x
        v_y = source_pt.geometry.y

        visited = set()
        self.traverse_upstream((v_x, v_y), visited)


    def traverse_upstream(self, coords: tuple, visited: set) -> None:
        '''
        Revise direction of edges via recursive depth-first search, starting from an
        outlet then traverse the graph "upstream". Visits every node that's connected to
        the initial source node.

        Parameters
        ----------
        coords : tuple
            Tuple of current (x, y) float coordinates. These coordinates are the
            name/index of the nodes in self.G
        visited : set
            Used to record which coordinates have already been visited in this search
        '''
        v = coords
        visited.add(v)
        for u in self.G.predecessors(v):
            if u not in visited:
                # Only retain edge from u -> v
                if self.G.has_edge(v, u):
                    assert self.G.has_edge(u, v)
                    self.G.remove_edge(v, u)
                self.traverse_upstream(u, visited)


    def add_edges(self, direction: str, verbose: bool=False)  -> None:
        '''
        Utilize user storm line data to add edges (and their nodes) to self.G in one or
        both directions

        Parameters
        ----------
        direction : str
            Direction to add edges in, based on the order of verticies in the user's
            stormwater infrastructure line data (self.lines & self.segments). Can be
            'both', 'original', or 'reverse'
        verbose : bool
            Set to True to print direction resolution/edge addition results to console
        '''
        if verbose:
            print('Adding edges...')

        if direction == 'both' or direction == 'original':
            self.segments['geometry'].apply(
                lambda seg: self.G.add_edge(seg.coords[0], seg.coords[1])
            )
        elif direction == 'both' or direction == 'reverse':
            self.segments['geometry'].apply(
                lambda seg: self.G.add_edge(seg.coords[1], seg.coords[0])
            )
        else:
            raise ValueError(
                f'direction "{direction}" is invalid, must be "both", "original", or '
                '"reverse"'
            )

        if verbose:
            if direction == 'original' or direction == 'reverse':
                print(f'Succesfully added {self.G.number_of_edges()} edges') 


    def resolve_from_sources(self, verbose: bool=False) -> None:
        '''
        Resolve directions of all edges within the graph by traversing subgraphs
        upstream from each flow source

        Parameters
        ----------
        verbose : bool (default False)
            Set to True to print direction resolution results to console
        '''
        self.add_edges(direction='both', verbose=verbose)

        source_pts = self.pts[self.pts['IS_SOURCE']]
        missing_pts = []

        for pt in source_pts.itertuples(name='StormPoint'):
            if not self.has_StormPoint(pt):
                missing_pts.append(pt.Index)
                continue
            self.resolve_upstream(pt)
        
        if verbose:
            if len(missing_pts) > 0:
                print(
                    'The following flow source points were not present in the graph, '
                    'ensure that they are properly snapped to a line vertex: ',
                    missing_pts
                )

            n_bidirectional = 0
            n_unidirectional = 0
            for u, v in self.G.edges():
                if self.G.has_edge(v, u):
                    n_bidirectional += 1
                else:
                    n_unidirectional += 1
            print(f'Succesfully resolved direction for {n_unidirectional} edges')
            if n_bidirectional > 0:
                print(f'Failed to resolve direction for {n_bidirectional/2} edges')


    def resolve_directions(
        self, method: str='from_sources', verbose: bool=False
    ) -> None:
        '''
        Attempt to resolve directions for all edges within the graph

        Parameters
        ----------
        method : str (default 'from_sources')
            Method to resolve edge directions for self.G, can be one of the following:
            - 'from_sources': Traverses upstream from each outlet point (where 
                self.pts['IS_SOURCE'] == True) to define edge directions to point to
                outlets
            - 'vertex_order': Defines edge directions using the order of verticies in
                self.lines 
            - 'vertex_order_r': Defines edge directions using reverse order of verticies
                in self.lines
        verbose : bool (default False)
            Set to True to print direction resolution results to console
        '''
        if method == 'from_sources':
            self.resolve_from_sources(verbose=verbose)
        elif method == 'vertex_order':
            self.add_edges(direction='original', verbose=verbose)
        elif method == 'vertex_order_r':
            self.add_edges(direction='reverse', verbose=verbose)
        else:
            raise ValueError(
                f'Method "{method}" is not a valid edge resolution method, must be '
                '"from_sources", "vertex_order", or "vertex_order_r".'
            )

        self.directions_resolved = True


    def get_outlet(self, pt_idx: int) -> Optional[int]:
        '''
        Get Index of the outlet for a given storm_pt whose coordinates exist in the
        graph

        Parameters
        ----------
        pt_idx : int
            Index of point, note that OBJECTID is the default index column
        '''
        if not self.directions_resolved:
            raise ValueError(
                f'Cannot get outlet until graph directions are resolved'
            )

        pt_x, pt_y = get_point_coords(self.pts.loc[pt_idx].geometry)
        if (pt_x, pt_y) not in self.G:
            warnings.warn(
                f'The point with index {pt_idx} does not have its coordinates as a '
                'node in the graph'
            )
            return None

        subG = nx.dfs_tree(self.G, (pt_x, pt_y))
        outlet_coords = [coords for coords, deg in subG.out_degree() if deg == 0]
        if len(outlet_coords) == 0:
            raise ValueError(f'Subgraph of point with index {pt_idx} has no outlet')
        elif len(outlet_coords) > 1:
            warnings.warn(
                f'Multiple outlet coordinates found for point with index {pt_idx}, '
                'only returning the first'
            )

        outlet_x, outlet_y = outlet_coords[0]
        outlet_pts = self.pts.cx[outlet_x, outlet_y] # gpd.GeoDataFrame
        if len(outlet_pts) == 0:
            return None
        elif len(outlet_pts) > 1:
            warnings.warn(
                f'Multiple outlet coordinates found for point with index {pt_idx}, '
                'only returning the first'
            )

        return outlet_pts.iloc[0].name


    def get_outlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        '''
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
        '''
        if catchment.crs != self.pts.crs:
            catchment = catchment.to_crs(crs=self.pts.crs)

        catchment_pts = gpd.clip(self.pts, catchment)
        sink_pts = catchment_pts[catchment_pts['IS_SINK']==True]

        indicies_to_remove = []
        sink_pt_inidicies = sink_pts.index.to_list()
        for idx in sink_pt_inidicies:
            outlet_idx = self.get_outlet(idx)
            if outlet_idx is not None and outlet_idx not in catchment_pts.index:
                indicies_to_remove.append(outlet_idx)
        
        return self.pts.loc[indicies_to_remove]


    def get_inlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        '''
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
        '''
        if not self.directions_resolved:
            raise ValueError(
                f'Cannot get inlet points until graph directions are resolved'
            )

        if catchment.crs != self.pts.crs:
            catchment = catchment.to_crs(crs=self.pts.crs)

        catchment_pts = gpd.clip(self.pts, catchment)
        source_pts = catchment_pts[catchment_pts['IS_SOURCE']==True]
        source_pt_geoms = source_pts.geometry.tolist()
        source_pt_coords = [get_point_coords(geom) for geom in source_pt_geoms]

        contrib_sink_inidices = set()
        for coords in source_pt_coords:
            tree = nx.bfs_tree(self.G, coords, reverse=True)

            for node in tree.nodes():
                if catchment.contains(Point(node)).any():
                    continue
                
                # Look for StormPoints at these coordinates
                pt = self.pts.cx[node[0], node[1]]
                if not pt.empty:
                    pt = self.to_StormPoint(pt)
                    contrib_sink_inidices.add(pt.Index)
        
        return self.pts.loc[list(contrib_sink_inidices)]


    def draw(
        self, extent: gpd.GeoDataFrame=None, ax=None, add_basemap: bool=False
    ) -> 'plt.axes':
        '''
        Draw the Graph using the geographic coordinates of each node

        Parameters
        ----------
        extent : gpd.GeoDataFrame (default None)
            GeoDataFrame whose extent will be used to trim the infrastructure data
        
        ax : plt.axes | None (default None)
            Matplotlib axes object to utilize for plot
        
        add_basemap : bool (deafult False)
            Option to add a contextily basemap to the plot
        '''
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        import numpy as np
        if add_basemap:
            import contextily as cx

        if ax is None:
            ax = plt.gca()
            ax.axis('equal')

        # Extent geometry
        if extent is not None:
            if extent.crs != self.crs:
                extent = extent.to_crs(self.crs)
            envelope = extent['geometry'].envelope.iloc[0]

        bidirectional_edges = []
        directional_edges = []
        for edge in self.G.edges():
            if extent is not None:
                # Exclude edges with no verticies within extent
                if not envelope.contains(Point(edge[0][0], edge[0][1])) and \
                    not envelope.contains(Point(edge[1][0], edge[1][1])):
                    continue
            if self.G.has_edge(edge[1], edge[0]):
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
                shape='left',
                width=0.1,
                head_width=2,
                length_includes_head=True,
                ec='darkblue',
                fc='cyan',
                zorder=1
            )

        # Plot bidirectional edges as segments
        lc = LineCollection([edge for edge in bidirectional_edges], color='darkblue')
        ax.add_collection(lc)

        if extent is not None:
            pts = gpd.clip(self.pts, extent['geometry'].envelope)
        else:
            pts = self.pts
        
        # Plot points
        sink_pts = pts[pts['IS_SINK']==True]
        source_pts = pts[pts['IS_SOURCE']==True]
        other_pts = pts[
            (pts['IS_SINK']==False) & (pts['IS_SOURCE']==False)
        ]
        sink_pts.plot(
            ax=ax, color='white', marker='s', edgecolor='black', markersize=10, zorder=2
        )
        source_pts.plot(
            ax=ax, color='white', marker='o', edgecolor='black', markersize=10, zorder=2
        )
        other_pts.plot(
            ax=ax, color='gray', marker='o', edgecolor='black', markersize=10, zorder=2
        )

        if add_basemap:
            try:
                cx.add_basemap(
                    ax, source=cx.providers.Esri.WorldImagery, crs=self.crs.to_string()
                )
            except Exception as e:
                warnings.warn(
                    'The following exception was raised while trying to add the'
                    'contextily basemap:', e
                )

        return ax
