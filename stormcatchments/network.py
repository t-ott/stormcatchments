from collections import namedtuple
import geopandas as gpd
import pandas as pd
import networkx as nx
from typing import Optional
from shapely.geometry import Point
import warnings

SINK_TYPES_VT = [   
    2, # Catchbasin
    8, # Culvert inlet
]

SOURCE_TYPES_VT = [
    5, # Outfall
    9, # Culvert outlet
]

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
        index_column: str
            Column name in both storm_lines and storm_pts 
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

        if index_column not in storm_lines.columns:
            raise ValueError(
                'storm_lines does not contain a column with provided index column '
                'name: {index_column}'
            )
        self.lines = storm_lines
        self.lines.set_index(index_column, inplace=True)

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

        if self.pts.crs != self.lines.crs:
            raise ValueError(
                'Coordinate reference systems of point and line datasets must match'
            )
        self.crs = self.pts.crs

        # Initialize empty Directional Graph, can consist many disconnected subgraphs
        self.G = nx.DiGraph()
    
    def get_lines_at_point(self, pt) -> gpd.GeoDataFrame:
        '''
        Return any infrastructure lines that touch this point

        It may be worth adding some sort of buffer / distance bubble if points aren't
        snapped perfectly to line verticies?
        
        pt : StormPoint (named tuple)
            The current stormwater infrastructure point feature
        '''
        assert pt.__class__.__name__ == 'StormPoint', f'Expected a "StormPoint" '\
            f'namedtuple, but got {pt.__class__.__name__}'
        
        x = pt.geometry.x
        y = pt.geometry.y

        return self.lines.cx[x, y]
    
    def get_line_coords(self, line) -> tuple:
        assert line.__class__.__name__ == 'StormLine', f'get_line_coords() expected ' \
            f'StormLine namedtuple, got {line.__class__.__name__}'

        line_x, line_y = line.geometry.coords.xy
        return line_x, line_y

    def add_infra_node(self, pt) -> None:
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

        self.G.add_node(oid, **pt_dict)

    def add_infra_edge(self, pt_start, pt_end) -> None:
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

    def get_outlet(self, pt_oid: int) -> int:
        '''
        Get OBJECTID(s) of the outlet(s) for a given storm_pt which exists in the graph.
        Ideally this return be single outlet point.

        Parameters
        ----------
        pt_oid: int
            OBJECTID of point
        '''
        assert pt_oid in self.G, f'The node "{pt_oid}" does not exist within the graph'
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

    def add_upstream_pts(self, downstream_pt) -> None:
        self._init_traverse(downstream_pt, True)
        return

    def find_downstream_pt(self, pt) -> Optional[gpd.GeoDataFrame]:
        downsteam_pt = self._init_traverse(pt, False)
        return downsteam_pt

    def _init_traverse(self, pt, traverse_upstream: bool) -> Optional[gpd.GeoDataFrame]:
        '''
        pt: gpd.GeoDataFrame | StormPoint namedtuple
        '''
        # TODO: Potentially just work this function into the main _traverse() function?
        # It seems unnecessary to seperate them?

        if type(pt) == gpd.GeoDataFrame:
            if len(pt) > 1:
                warnings.warn(
                    '_init_traverse() got multiple points, only keeping the first'
                )
            pt_iter = pt.itertuples(name='StormPoint')
            pt = next(pt_iter)
        elif type(pt) == pd.Series:
            # convert to StormPoint namedtuple
            field_names = self.pts.columns.to_list()
            field_names.insert(0, 'Index')
            pt = namedtuple('StormPoint', field_names)(pt.name, *pt)
        else:
            assert pt.__class__.__name__ == 'StormPoint', f'Expected pt to be a ' \
                'gpd.GeoDataFrame or a StormPoint namedtuple, got a ' \
                f'{pt.__class__.__name__}'
        
        lines = self.get_lines_at_point(pt)
        if len(lines) < 1:
            print(f'No lines connect to point with OBJECTID: {pt.Index}')
            return

        for line in lines.itertuples(name='StormLine'):
            line_oid = line.Index
            line_x, line_y = self.get_line_coords(line)

            # enter network traverse function, potential recursion here
            return_pt = self._traverse(
                pt, line_oid, (line_x, line_y), True, traverse_upstream
            )
            
            if return_pt is not None:
                # Found a downstream point
                return return_pt

        return return_pt


    def _traverse(
        self,
        current_pt,
        line_oid: int,
        line_coords: tuple,
        new_line: bool,
        traverse_upstream: bool,
    ) -> Optional[gpd.GeoDataFrame]:
        '''
        Find any pts upstream or downstream of the current point along the current line.
        If traversing upstream, these will be the added as the next upstream node(s) in
        the current graph.

        This is a destructive process, going from the bottom of the line, traversing
        upwards and removing the old verticies from the line as we go

        Parameters
        ----------
        current_pt: StormPoint
            The current point feature, for which this function will find the next
            point(s) for, and optionally add them to the current graph if traversing
            upstream

        line_oid: int
            OBJECTID integer value for the current line feature

        line_coords: tuple
            Tuple containing two lists of equal length, with the first containing the
            x-coordinates of all the verticies in the line, the second containing the
            y-coordinates

        new_line: bool
            True/False to determine if line is being worked on, or if line coordinates
            need to be extracted and ordered

        traverse_upstream: bool
            If True, will add each sucessive upstream point to the current graph

        Returns
        -------
        None | next_pt: gpd.GeoDataFrame
            If traversing upstream, returns None. If traversing downstream, returns 
            next_pt (gpd.GeoDataFrame) which represents an identified downstream point.
            Can also return None if no downstream point is found while traversing
            downstream.
        '''

        if traverse_upstream:
            # initalize subgraph
            self.add_infra_node(current_pt)

        line_x, line_y = line_coords

        if new_line:
            # order the line verticies so that we can iterate upstream 
            current_pt_x = current_pt.geometry.x
            current_pt_y = current_pt.geometry.y

            assert (current_pt_x in line_x) and (current_pt_y in line_y), 'Could not ' \
                'find current point within the line coordinates'

            x_index = line_x.index(current_pt_x)
            y_index = line_y.index(current_pt_y)
            assert x_index == y_index
            # TODO: Think of a way to address this:
            # This could fail to find the CORRECT index of the downstream point within the
            # cooridnates of the current line. This could happen in if verticies along the
            # line share the exact same x coordinates (for example) but have different
            # y coordinates

            if x_index != 0:
                # downstream point is not listed first in the line coordinates
                line_x.reverse()
                line_y.reverse()

            # now line coords are ordered downstream -> upstream
            # remove starting coordinate from line
            del line_x[0]
            del line_y[0]

        # iterate through line coords to find next nodes
        for i, (x, y) in enumerate(zip(line_x, line_y)):
            # try to find a storm_pt with coordinates at this vertex

            # TODO: Allow for some sort of buffer here if points are not snapped?
            # TODO: Also search for points that are snapped to the line, but aren't
            # snapped to a vertex?

            next_pt = self.pts.cx[x, y] # gpd.GeoDataFrame

            if len(next_pt) == 0:
                # TODO: Can either assign a new point here to represnt a line vertex
                # with no corresponding StormPoint. Or can end the traverse of this
                # line here, which would only allow line verticies that have StormPoints
                # on them into the graph. Could end here with:
                # return
                
                # TODO: Assigning a new_oid here can be risky if graphs are to be
                # reused. What if a user wants to take a big graph that was previously
                # generated and saved, then expand it with neighboring data? Then
                # certain values for these verticies may have been assigned OBJECTIDs
                # that are represented as actual storm points in the new data. An
                # alternate way of approaching this is giving these points an OBJECTID
                # of 0, then checking for membership in the graph by geometry.

                # Add a point to self.pts for this vertex
                new_oid = self.pts.index.max() + 1
                new_pt = {
                    'Type': 0,
                    'IS_SINK': False,
                    'IS_SOURCE': False,
                    'geometry': Point(x, y),
                }
                self.pts.loc[new_oid] = new_pt
                new_pt['Index'] = new_oid
                # convert this to StormPoint namedtuple
                next_pt = namedtuple('StormPoint', new_pt.keys())(*new_pt.values())
            elif len(next_pt) > 0:
                if len(next_pt) > 1:
                    warnings.warn(
                        'Found more than one point at stormline vertex, only keeping '
                        f'the first point with OBJECTID {next_pt.index.min()}'
                    )
                pt_iter = next_pt.itertuples(name='StormPoint')
                next_pt = next(pt_iter)

            if traverse_upstream:
                # add new node and edge from next_pt -> current_pt
                self.add_infra_node(next_pt)
                self.add_infra_edge(next_pt, current_pt)
            elif next_pt.IS_SOURCE:
                # traversing downstream and just found an outlet point
                return next_pt

            # remove the coord from the line points
            del line_x[i]
            del line_y[i]

            if len(line_x) == 0:
                # no more verticies along line to inspect
                assert len(line_x) == len(line_y), 'Lists of x and y coordinates for '\
                    'the current line are unequal in length'

                # find next line(s)
                lines = self.get_lines_at_point(next_pt)
                # but get rid of current line, since we already traversed it
                lines = lines.drop(line_oid)

                for line in lines.itertuples(name='StormLine'):
                    line_oid = line.Index
                    line_x, line_y = self.get_line_coords(line)

                    # TODO: What would happen if a network had multiple outlet points?
                    # only the last outlet point found would be returned it seems. is
                    # this a problem?

                    # recursively call search on each of these new lines
                    return_pt = self._traverse(
                        next_pt, line_oid, (line_x, line_y), True, traverse_upstream
                    )
                    if return_pt is not None:
                        return return_pt
    
            else:
                # recursively call search
                self._traverse(
                    next_pt, line_oid, (line_x, line_y), False, traverse_upstream
                )
                # TODO: Conditionally return a value if return_pt is not None?

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
            if outlet_oid not in catchment_pts.index:
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
        subG_node: int
            Name (OBJECTID) of node for which only its connected nodes will be drawn.
            Any nodes without a path to subG_node will therefore not be drawn.
        
        ax: plt.axes | None
        
        add_basemap: bool
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
            [geom.x, geom.y] for pt, geom in 
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
