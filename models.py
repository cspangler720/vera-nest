# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from dataclasses import dataclass

import cadquery as cq
from shapely.ops import unary_union
from shapely.geometry import Polygon, box

from util import get_solids

@dataclass
class PartData:
    """Captures the filename, cadquery reference (part), nesting profile (footprint), and a  and thickness value of a part"""
    # this allows the loader module to create a list of part data's 
    filename: str
    part: cq.Workplane
    footprint: Polygon
    thickness: float

    def planar_projection(self): # probably should wrap into the initalization
        solids = sorted(get_solids(self.part), key=lambda s: s.Volume(), reverse=True)
        if not solids:
            raise ValueError("No solids found in the model.")
        solid = solids[0]

        # Get the top face (highest z)
        face = sorted(solid.Faces(), key=lambda f: f.Center().z)[-1]

        shapely_polygons = []
        for wire in face.Wires():
            points = [(v.X, v.Y) for v in wire.Vertices()]
            if len(points) >= 3:
                try:
                    poly = Polygon(points)
                    if poly.is_valid:
                        shapely_polygons.append(poly)
                    else:
                        print(f"Invalid polygon: {poly}")
                except Exception as e:
                    print(f"Error creating polygon: {e}")
                    continue

        if not shapely_polygons:
            bbox = solid.BoundingBox()
            return box(bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax)

        footprint = unary_union(shapely_polygons)
        return footprint

""" this is here in case I the new one has some hidden error I don't see
    def planar_projection_old(self, model):
            
        solids = get_solids(model) 
        # could do the planar projection for each solid in the list
        solid = solids[0] # should be largest model (idk through)

        # top face on x-y plane
        face = sorted(solid.Faces(), key=lambda f: f.Center().z)[-1]
        
        shapely_polygons = []
        for wire in face.Wires():
            # I need to make sure this is actually getting unique points in order
            points = [(v.X, v.Y) for v in wire.Vertices()]
            if len(points) >= 3: # shapely requires at least 3 points to form a ring
                try:
                    poly = Polygon(points)
                    if poly.is_valid:
                        shapely_polygons.append(poly)
                except Exception:
                    continue
        
        if not shapely_polygons:
            # fallback to bounding box projection if face extraction fails
            bbox = solid.BoundingBox()
            return box(bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax)
            
        footprint = shapely_polygons[0] 
        for p in shapely_polygons[1:]: # fills internal contours
            footprint = footprint.symmetric_difference(p)
            
        return footprint.convex_hull if footprint.geom_type == 'MultiPolygon' else footprint
"""

@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    height: float


class Sheet: 
    """Represents a sheet metal"""
    # ideally this can be used for custom sheets
    # the plan is to have a user-json file containing the avialable sheets and remnants
    # the json would contian data to initalize these objects to a dictionary

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.occupied = []  # List of occupied rectangles

    def can_place(self, rect):
        new_rect = Rectangle(rect.x, rect.y, rect.width, rect.height)
        for occ in self.occupied:
            if (new_rect.x < occ.x + occ.width and
                new_rect.x + new_rect.width > occ.x and
                new_rect.y < occ.y + occ.height and
                new_rect.y + new_rect.height > occ.y):
                return False
        return True

    def place(self, rect):
        if self.can_place(rect):
            self.occupied.append(rect)
            return True
        return False
    

class Workspace:
    """Nesting workspace"""
    def __init__(self):
        self.parts = []
    # wip, I would like to capture more stuff in this 