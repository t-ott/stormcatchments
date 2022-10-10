from collections import namedtuple
import geopandas as gpd
import pandas as pd
import networkx as nx
from typing import Optional
from shapely.geometry import LineString, MultiPoint, Point
import warnings

SINK_TYPES_VT = [   
    2, # Catchbasin
    8, # Culvert inlet
]

SOURCE_TYPES_VT = [
    5, # Outfall
    9, # Culvert outlet
]

def get_point_coords(pt_geom, decimals: int=None) -> tuple:
    '''
    Get and x, y coordinate tuple from a Point or MultiPoint shapely geometry

    Parameters
    ----------
    pt_geom: Point | MultiPoint
        shapely geometry object
    decimals: int (default None)
        Decimals to round coordinates to
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
    lines : gpd.GeoDataFrame
        All the stormwater infrastructure line features within the area of interest
    pts : gpd.GeoDataFrame
        All the stormwater infrastructure point features within the area of interest
    G : list
        A list of all the graphs generated within the area of interest
    crs : pyproj.crs.crs.CRS
        The PyProj Coordinate Reference System of infrastructure data
    '''
    def __init__(
        self,
        storm_lines: gpd.GeoDataFrame,
        storm_pts: gpd.GeoDataFrame,
        coord_decimals: int=3,
        index_column: str='OBJECTID',
        type_column: str='Type',
        sink_types: list=SINK_TYPES_VT,
        source_types: list=SOURCE_TYPES_VT,
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
        index_column: str
            Column name in storm_pts 
        type_column: str
            Column in storm_pts GeoDataFrame that represents the type of each point
            (e.g., catchbasins, outfalls, culverts)
        is_sink_types: list
            List of type values that correspond to flow sinks, where flow enters at
            these points, such as a catchbasin
        is_source_types: list
            List of type values that correspond to flow sources, where flow exits at
            these points, such as an outfall 
        '''
        # print('Initializing Network...')
        if storm_pts.crs != storm_lines.crs:
            raise ValueError(
                'Coordinate reference systems of point and line datasets must match'
            )
        self.crs = storm_pts.crs

        # TODO: Remove this
        # import matplotlib.pyplot as plt
        # self.lines.plot()
        # plt.show()

        # Explode all lines into 2-vertex segments, add these as edges in a directional
        # graph with coordinate tuples as nodes. The DiGraph will initialize with two
        # edges connecting each node pair, one in each direction. Direction will be
        # revised later
        self.G = nx.DiGraph()
        all_segments = []
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
            
            for u, v in zip(u_coords, v_coords):
                self.G.add_edge(u, v)
                self.G.add_edge(v, u)

            segments = list(map(LineString, zip(u_coords, v_coords)))
            all_segments.extend(segments)

        lines = gpd.GeoSeries(all_segments)
        self.lines = gpd.GeoDataFrame(geometry=lines).set_crs(storm_lines.crs)
        # self.lines = storm_lines

        if index_column not in storm_pts.columns:
            raise ValueError(
                'storm_pts does not contain a column with provided index column '
                f'name: {index_column}'
            )
        elif type_column not in storm_pts.columns:
            raise ValueError(
                'storm_pts does not contain a column with the provided type column '
                f'name: {type_column}'
            )
        self.pts = storm_pts
        self.pts.set_index(index_column, inplace=True)

        if 'IS_SINK' in storm_pts.columns:
            if storm_pts.dtypes['IS_SINK'] != bool:
                raise ValueError('storm_pts column "IS_SINK" must be bool dtype')
        else:
            self.pts['IS_SINK'] = self.pts[type_column].apply(
                lambda x: True if x in sink_types else False
            )

        if 'IS_SOURCE' in storm_pts.columns:
            if storm_pts.dtypes['IS_SOURCE'] != bool:
                raise ValueError('storm_pts column "IS_SOURCE" must be bool dtype')
        else:
            self.pts['IS_SOURCE'] = self.pts[type_column].apply(
                lambda x: True if x in source_types else False
            )

        # Round all point coordinate values
        self.pts['geometry'] = self.pts['geometry'].apply(
            lambda geom: Point([get_point_coords(geom, coord_decimals)])
        )
        
        # TODO: Remove this
        # ax = self.lines.plot()
        # self.pts.plot(ax=ax)
        # plt.show()
    
    def get_lines_at_point(self, pt, exclude_line: int=None) -> gpd.GeoDataFrame:
        '''
        Return any infrastructure lines that touch this point

        It may be worth adding some sort of buffer / distance bubble if points aren't
        snapped perfectly to line verticies?
        
        pt : StormPoint (named tuple)
            The current stormwater infrastructure point feature
        '''
        assert pt.__class__.__name__ == 'StormPoint', f'Expected a "StormPoint" '\
            f'namedtuple, but got {pt.__class__.__name__}'
        x, y = get_point_coords(pt)

        lines = self.lines.cx[x, y]
        if exclude_line is not None:
            lines = lines.drop(exclude_line)
        return lines

    def get_lines_at_coords(self, coords: tuple, exclude_line: int=None) -> gpd.GeoDataFrame:
        x, y = coords
        lines = self.lines.cx[x, y]
        if exclude_line is not None:
            lines = lines.drop(exclude_line)
        return lines
    
    def get_line_coords(self, line) -> tuple:
        assert line.__class__.__name__ == 'StormLine', f'get_line_coords() expected ' \
            f'StormLine namedtuple, got {line.__class__.__name__}'

        line_x, line_y = line.geometry.coords.xy
        return line_x, line_y

    def add_infra_node(self, pt: 'StormPoint') -> None:
        '''
        Add a point as a node in the graph

        Parameters
        ----------
        pt: StormPoint namedtuple
        '''
        # oid will be the "name"/index of the node in the graph
        oid = pt.Index

        # keep all other columns from row that aren't OBJECTID in node's attributes
        pt_dict = pt._asdict()
        del pt_dict['Index']

        if isinstance(pt_dict['geometry'], MultiPoint):
            pt_dict['geometry'] = Point(
                pt_dict['geometry'].geoms[0].x, pt_dict['geometry'].geoms[0].y
            )

        self.G.add_node(oid, **pt_dict)

    def add_infra_edge(self, pt_start: 'StormPoint', pt_end: 'StormPoint') -> None:
        '''
        Parameters
        ----------
        pt_start: StormPoint namedtuple
        pt_end: StormPoint namedtupe
        '''
        # connect both points 
        pt_start_oid = pt_start.Index
        pt_end_oid = pt_end.Index
        self.G.add_edge(pt_start_oid, pt_end_oid)

    def get_outlet(self, pt_oid: int) -> Optional[int]:
        '''
        Get OBJECTID(s) of the outlet(s) for a given storm_pt which exists in the graph.
        Ideally this return be single outlet point.

        Parameters
        ----------
        pt_oid: int
            OBJECTID of point
        '''
        if pt_oid not in self.G:
            print(f'The point {pt_oid} is not a node in the graph')
            return

        subG = nx.dfs_tree(self.G, pt_oid)
        outlets = [oid for oid, deg in subG.out_degree() if deg == 0]
        if len(outlets) == 0:
            raise ValueError('Subgraph has no outlet.')
        elif len(outlets) > 1:
            warnings.warn(
                f'Multiple outlets found for point with OBJECTID {pt_oid}, only '
                'returning the first.'
            )
        return outlets[0]

    def to_StormPoint(self, pt) -> 'StormPoint':
        if isinstance(pt, gpd.GeoDataFrame):
            if len(pt) > 1:
                warnings.warn(
                    '_init_traverse() got multiple points, only keeping the first'
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
                'gpd.GeoDataFrame or a StormPoint namedtuple, got a ' \
                f'{pt.__class__.__name__}'
        return pt

    def find_downstream_pt(self, pt) -> Optional[gpd.GeoDataFrame]:
        print('Finding downstream point...')
        pt = self.to_StormPoint(pt)
        pt_x = pt.geometry.x
        pt_y = pt.geometry.y

        visited = set()
        downstream_pt = self.traverse_downstream((pt_x, pt_y), visited)
        return downstream_pt

    def traverse_downstream(self, coords: tuple, visited: set=None) -> Optional[gpd.GeoDataFrame]:
        '''Utilize depth-first search to find an outfall/outlet point, '''
        x, y = coords
        visited.add((x, y))

        for n in self.G.neighbors((x, y)):
            n_pt = self.pts.cx[n[0], n[1]]
            if not n_pt.empty:
                n_pt = self.to_StormPoint(n_pt)
                if n_pt.IS_SOURCE:
                    # search complete
                    return n_pt
            if n not in visited:
                downstream_pt = self.traverse_downstream(n, visited)
                if downstream_pt is not None:
                    return downstream_pt

    def resolve_direction(self, source_pt):
        source_pt = self.to_StormPoint(source_pt)
        v_x = source_pt.geometry.x
        v_y = source_pt.geometry.y

        visited = set()
        self.traverse_upstream((v_x, v_y), visited)

    def traverse_upstream(self, coords: tuple, visited: set=None) -> None:
        '''
        Revise direction of edges via depth-first search, starting from an outlet
        '''
        if visited is None:
            visited = set()

        v = coords
        visited.add(v)
        for u in self.G.predecessors(v):
            if u not in visited:
                self.G.remove_edge(v, u)
                self.traverse_upstream(u, visited)

    def get_outlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        '''
        Get GeoDataFrame of all the infrastructure points within the catchment that
        bring flow out of the current catchment. The catchments for these points will
        need to be removed from current catchment.

        Parameters
        ----------
        catchment: gpd.GeoDataFrame
            GeoDataFrame containing the current catchment polygon
        '''
        if catchment.crs != self.pts.crs:
            catchment = catchment.to_crs(crs=self.pts.crs)

        catchment_pts = gpd.clip(self.pts, catchment)
        sink_pts = catchment_pts[catchment_pts['IS_SINK']==True]
        sink_pt_oids = sink_pts.index.tolist()

        oids_to_remove = []
        for sink_pt_oid in sink_pt_oids:
            outlet_oid = self.get_outlet(sink_pt_oid)
            if outlet_oid is not None and outlet_oid not in catchment_pts.index:
                oids_to_remove.append(sink_pt_oid)
        
        return self.pts.loc[oids_to_remove]

    def get_inlet_points(self, catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        '''
        Get GeoDataFrame of all the infrastructure points outside the catchment that
        bring flow into the catchment.

        Parameters
        ----------
        catchment: gpd.GeoDataFrame
            GeoDataFrame containing the current catchment polygon

        Returns
        -------
        inlet_pts: gpd.GeoDataFrame
            GeoDataFrame containing all the points outside the catchment that bring flow
            into the catchment
        '''
        if catchment.crs != self.pts.crs:
            catchment = catchment.to_crs(crs=self.pts.crs)

        catchment_pts = gpd.clip(self.pts, catchment)
        source_pts = catchment_pts[catchment_pts['IS_SOURCE']==True]
        source_pt_oids = source_pts.index.tolist()
        
        # get subgraphs for each source_pt
        source_subGs = []
        for subG in nx.weakly_connected_components(self.G):
            for source_pt_oid in source_pt_oids:
                if source_pt_oid in subG:
                    source_subGs.append(subG)
        
        # find points from each subgraph that contribute flow to current catchment
        oids_to_add = []
        for subG in source_subGs:
            for node in subG:
                if node in catchment_pts.index:
                    continue
                if self.pts.at[node, 'IS_SINK']:
                    oids_to_add.append(node)
        
        return self.pts.loc[oids_to_add]
     
    def generate_catchment_graphs(self, catchment: gpd.GeoDataFrame) -> None:
        '''
        Generate graph representations of all infrastructure networks that are within or
        partially within a catchment.

        Parameters
        ----------
        catchment: gpd.GeoSeries
            A GeoPandas GeoSeries with the catchment geometry
        '''
        # ensure CRS match
        if catchment.crs != self.pts.crs:
            catchment = catchment.to_crs(crs=self.pts.crs)

        pts = gpd.clip(self.pts, catchment)
        
        # Look for all downstream points connected to this catchment's infrastructure
        downstream_pts = []
        for pt in pts.itertuples(name='StormPoint'):
            if pt.Index in self.G:
                continue
            if pt.IS_SOURCE:
                # is an outlet point, may bring flow into the catchment
                self.add_upstream_pts(pt)
            else:
                downstream_pt = self.find_downstream_pt(pt)
                if downstream_pt is not None:
                    downstream_pts.append(downstream_pt)

        # Traverse all the downstream points upstream to build their subgraphs
        for pt in downstream_pts:
            # Skip if already in a graph
            if pt.Index in self.G:
                continue
            else:
                self.add_upstream_pts(pt)

    def draw_G(self, subG_node: int=None, ax=None, add_basemap=True) -> 'plt.axes':
        '''
        Draw the Graph using the geographic coordinates of each node

        Parameters
        ----------
        subG_node: int (default None)
            Name (OBJECTID) of node for which only its connected nodes will be drawn.
            Any nodes without a path to subG_node will therefore not be drawn.
        
        ax: plt.axes | None (default None)
        
        add_basemap: bool (deafult True)
            Option to add a contextily basemap to the plot
        '''
        import matplotlib.pyplot as plt
        import numpy as np
        if add_basemap:
            import contextily as cx

        if ax is None:
            ax = plt.gca()
            ax.axis('equal')

        # Plot edges as arrows
        for edge in self.G.edges():
            u_geom = self.G.nodes[edge[0]]['geometry']
            v_geom = self.G.nodes[edge[1]]['geometry']
            ax.arrow(
                u_geom.x,
                u_geom.y,
                v_geom.x - u_geom.x,
                v_geom.y - u_geom.y,
                width=0.1,
                head_width=1,
                length_includes_head=True,
                ec='red',
                fc='red',
                zorder=1
            )

        coords = np.array([
            [geom.x, geom.y] for _, geom in 
            nx.get_node_attributes(self.G, 'geometry').items()
        ])
        pt_type = np.array([
            pt_type for _, pt_type in nx.get_node_attributes(self.G, 'Type').items()
        ])
        # Plot nodes 
        ax.scatter(coords[:, 0], coords[:, 1], c=pt_type, marker='s', s=5, zorder=2)

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
