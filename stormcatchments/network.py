from collections import namedtuple
import geopandas as gpd
import networkx as nx
import pandas as pd
from typing import Optional
import warnings

import matplotlib.pyplot as plt

# 0 = Flow enters at point
# 1 = Flow exits at point
# 2 = Flow neither enters or exits at point
STORM_PT_FLOWS = {
    2: 0, # Catchbasin
    3: 2, # Stormwater manhole
    5: 1, # Outfall
    8: 0, # Culvert inlet
    9: 1, # Culvert outlet
}

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
    Gs : list
        A list of all the graphs generated within the area of interest
    currentG : None | nx.DiGraph
        The current networkx directional graph being generated. Once finished, it
        will be appended to Gs
    '''
    def __init__(self, storm_lines: gpd.GeoDataFrame, storm_pts: gpd.GeoDataFrame):
        '''
        Parameters:
        ----------
        storm_lines : gpd.GeoDataFrame
            All the stormwater infrastructure line features within the area of interest
        storm_pts : gpd.GeoDataFrame
            All the stormwater infrastructure points features within the area of interest
        '''
        print('Initializing Network...')

        assert 'OBJECTID' in storm_lines.columns, f'storm_lines must contain a column '\
            'named OBJECTID'
        self.lines = storm_lines
        
        assert 'OBJECTID' in storm_pts.columns, f'storm_pts must contain a column '\
            'named OBJECTID'
        assert 'Type' in storm_pts.columns, f'storm_pts must contain a column '\
            'named Type'
        
        self.pts = storm_pts
        if 'flow' in self.pts.columns:
            flow_vals = storm_pts['flow'].unique().tolist()
            assert sorted(flow_vals) == [0, 1, 2], f'Column "flow" in storm_pts' \
                'must only contain values [0, 1, 2]'
        else:
            self.pts['flow'] = self.pts['Type'].map(STORM_PT_FLOWS).fillna(2)
        
        self.Gs = []
        self.currentG = None
        self.pt_oids = []
    
    def get_lines_at_point(self, pt):
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
    
    def get_line_coords(self, line):
        assert line.__class__.__name__ == 'StormLine', f'get_line_coords() expected ' \
            f'StormLine namedtuple, got {line.__class__.__name__}'

        line_x, line_y = line.geometry.coords.xy
        return line_x, line_y

    def add_infra_node(self, pt):
        '''pt: StormPoint'''
        # oid will be the "name"/index of the node in the graph
        oid = pt.OBJECTID
        self.pt_oids.append(oid) # add to running list of all OIDs

        # keep all other columns from row that aren't OBJECTID in node's attributes
        pt_dict = pt._asdict()
        del pt_dict['OBJECTID']

        self.currentG.add_node(oid, **pt_dict)

    def add_infra_edge(self, pt_start, pt_end):
        '''
        pt_start: StormPoint
        
        pt_end: StormPoint
        '''
        # connect both points 
        pt_start_oid = pt_start.OBJECTID
        pt_end_oid = pt_end.OBJECTID
        self.currentG.add_edge(pt_start_oid, pt_end_oid)

    def add_upstream_pts(self, downstream_pt) -> None:
        # line_oid, line_x, line_y = self._get_traverse_args(downstream_pt)
        # self._traverse(downstream_pt, line_oid, (line_x, line_y), True, True)
        # self._init_traverse(downsteam_pt)
        self._init_traverse(downstream_pt, True)
        # Reset currentG
        self.Gs.append(self.currentG)
        self.currentG = None
        return

    def find_downstream_pt(self, pt) -> Optional[gpd.GeoDataFrame]:
        # line_oid, line_x, line_y = self._get_traverse_args(pt)
        # return self._traverse(pt, line_oid, (line_x, line_y), True, False)
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
            pt_iter = pt.itertuples(index=False, name='StormPoint')
            pt = next(pt_iter)
        else:
            assert pt.__class__.__name__ == 'StormPoint', f'Expected pt to be a ' \
                'gpd.GeoDataFrame or a StormPoint namedtuple, got a ' \
                f'{pt.__class__.__name__}'
        
        lines = self.get_lines_at_point(pt)
        if len(lines) < 1:
            print(f'No lines connect to point with OBJECTID: {pt.OBJECTID}')
            return

        for line in lines.itertuples(index=False, name='StormLine'):
            # print('Starting new line...')
            line_oid = line.OBJECTID
            line_x, line_y = self.get_line_coords(line)

            # enter network traverse function, potential recursion here
            return_pt = self._traverse(
                pt, line_oid, (line_x, line_y), True, traverse_upstream
            )
            
            if return_pt is not None:
                # Found a downstream point
                return return_pt
            # print('Got a return point:')
            # print(return_pt)
        
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

        '''
        # TODO: Remove extra comments/prints
        # print('\nStarting _traverse()')
        # print(f'type of current_pt: {type(current_pt)}')

        if traverse_upstream and self.currentG is None:
            # initialize currentG
            self.currentG = nx.DiGraph()
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
            # This could fail to find the CORRECT index of the downstream point within the
            # cooridnates of the current line. This could happen in if verticies along the
            # line share the exact same x coordinates (for example) but have different
            # y coordinates
            # TODO: Think of a way to address this

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
            next_pt = self.pts.cx[x, y] # gpd.GeoDataFrame

            if len(next_pt) == 0:
                # print('Did not find point at line vertex')
                # TODO: Could still add an empty node here? Sometimes there will be
                # verticies along lines that have no point features right on the vertex
                return
            elif len(next_pt) > 1:
                warnings.warn(
                    'Found more than one point at stormline vertex, only keeping '
                    f'point with OBJECTID {next_pt.iloc[0].OBJECTID}'
                )
            # next_pt = next_pt.iloc[0] # pd.Series
            # print(type(next_pt))
            
            pt_iter = next_pt.itertuples(index=False, name='StormPoint')
            next_pt = next(pt_iter)
            # next_pt = [pt for pt in next_pt.itertuples(name='StormPoint')]
            # print(type(next_pt[0]))

            if traverse_upstream:
                # adding edge from next_pt -> current_pt
                self.add_infra_node(next_pt)
                self.add_infra_edge(next_pt, current_pt)
            elif next_pt.flow == 1:
                # traversing downstream and just found an outlet point
                # print('Found an outlet point')
                return next_pt

            # remove the coord from the line points
            del line_x[i]
            del line_y[i]

            if len(line_x) == 0:
                # no more verticies along line to inspect
                assert len(line_x) == len(line_y), 'Lists of x and y coordinates for '\
                    'the current line are unequal in length'

                # print('Done with line, going to next line')
                # find next line(s)
                lines = self.get_lines_at_point(next_pt)
                # but get rid of current line, since we already traversed it
                lines = lines[lines['OBJECTID'] != line_oid]

                # assert lines.columns[0] == 'OBJECTID'

                for line in lines.itertuples(index=False, name='StormLine'):
                    line_oid = line.OBJECTID
                    line_x, line_y = self.get_line_coords(line)

                    # TODO: What would happen if a newtork had multiple outlet points?
                    # only the last outlet point found would be returned it seems. is
                    # this a problem?

                    # recursively call search on each of these new lines
                    self._traverse(
                        next_pt, line_oid, (line_x, line_y), True, traverse_upstream
                    )
    
            else:
                # recursively call search
                self._traverse(
                    next_pt, line_oid, (line_x, line_y), False, traverse_upstream
                )
        
    def generate_catchment_graphs(self, catchment: gpd.GeoSeries) -> None:
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
            if pt.OBJECTID in self.pt_oids:
                continue

            if pt.flow == 1:
                # is an outlet point, may bring flow into the catchment
                self.add_upstream_pts(pt)

            # print(f'Looking for downstream point for pt: {pt.OBJECTID}')
            downstream_pt = self.find_downstream_pt(pt)

            # if downstream_pt is None:
            #     print('Did not find downstream point...')
            # else:
            #     print('Found the following downstream point...')
            #     print(downstream_pt)
            #     print('\n')

            if downstream_pt is not None:
                downstream_pts.append(downstream_pt)

        # Traverse all the downstream points upstream to build their networks
        for pt in downstream_pts:
            print(f'Adding upstream points for pt {pt.OBJECTID}')
            # Skip if already in a graph
            if pt.OBJECTID in self.pt_oids:
                continue
            else:
                self.add_upstream_pts(pt)

        # print(f'self.Gs: {self.Gs}')
        # for G in self.Gs:
        #     nx.draw(G)
        #     plt.show()

        # self.add_upstream_pts(downstream_pt)
        # print(pt)

    def get_outlet_points(self, catchment: gpd.GeoSeries) -> gpd.GeoDataFrame:
        '''
        Get GeoDataFrame of all the infrastructure points within the catchment that
        bring flow out of the current catchment. The catchments for these points will
        need to be removed from current catchment
        '''
        return

    def get_inlet_points(self, catchment: gpd.GeoSeries) -> gpd.GeoDataFrame:
        '''
        Get GeoDataFrame of all the infrastructure points outside the catchment that
        bring flow into the catchment.
        '''
        return
