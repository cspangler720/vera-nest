# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

import os
from typing import List, Tuple, Dict

import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, box
from shapely.affinity import translate, rotate

import models
from util import get_solids

def group_thickness(parts_data: List[models.PartData]) -> Dict[float, List[models.PartData]]:
    thickness_groups: Dict[float, List[models.PartData]] = {}
    for part_data in parts_data:
        thickness = round(part_data.thickness, 4)
        if thickness not in thickness_groups:
            thickness_groups[thickness] = []
        thickness_groups[thickness].append(part_data)
    return thickness_groups

def bounding_box(solid: cq.Workplane.solids) -> Tuple[float, float]:
    bbox = solid.BoundingBox() 
    return bbox.xlen, bbox.ylen


def area(part_data: models.PartData) -> float:  
    width, height = bounding_box(get_solids(part_data.part)[0])
    return width * height


def sort(parts_data: List[models.PartData]) -> List[models.PartData]:
    return sorted(parts_data, key=area, reverse=True)


def planar_projection(model: cq.Workplane) -> Polygon:
    solids = get_solids(model)
    solid = solids[0]
    
    # top face on x-y plane
    face = sorted(solid.Faces(), key=lambda f: f.Center().z)[-1]
    
    shapely_polygons = []
    for wire in face.Wires():
        # need to make sure this is actually getting unique points in order
        points = [(v.X, v.Y) for v in wire.Vertices()]
        
        # shapely requires at least 3 points to form a ring
        if len(points) >= 3:
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
        
    # fill internal contours
    footprint = shapely_polygons[0]
    for p in shapely_polygons[1:]:
        footprint = footprint.symmetric_difference(p)
        
    return footprint.convex_hull if footprint.geom_type == 'MultiPolygon' else footprint


def place_part(part: Polygon, bin_polygon: Polygon, 
               placed_parts: List[Polygon], 
               tolerance: float,
               pad: float
               ) -> Tuple[float, float, float, bool]:
    
    padded_part = part.buffer(pad)
    bin_minx, bin_miny, bin_maxx, bin_maxy = bin_polygon.bounds
    
    for angle in [0, 90, 180, 270]:
        rotated_part = rotate(padded_part, angle, origin='center')
        p_minx, p_miny, p_maxx, p_maxy = rotated_part.bounds
        w, h = p_maxx - p_minx, p_maxy - p_miny
        
        # scan bin using the bounds of the padded part
        for x in np.arange(bin_minx, bin_maxx - w, tolerance):
            for y in np.arange(bin_miny, bin_maxy - h, tolerance):
                candidate = translate(rotated_part, xoff=x-p_minx, yoff=y-p_miny)
                
                # check if the padded version fits without hitting other padded versions
                if candidate.within(bin_polygon) and not any(candidate.intersects(p) for p in placed_parts):
                    return (x - p_minx, y - p_miny, angle, True)
                    
    return (0, 0, 0, False)


def align_z(part: cq.Workplane) -> cq.Workplane:
    """Align z-axis and set bottom of part to z=0"""
    # currently this is not working because something in the truenest
    # function breaks the z-alignement
    # further this cannot be used in model_nest because it
    # can cause unexpected rotations 
    solids = part.solids().vals()
    aligned_solids = []
    
    target = np.array([0, 0, -1])

    for solid in solids:
        f = max(solid.Faces(), key=lambda f: f.Area())
        n_val = f.normalAt()
        n = np.array([n_val.x, n_val.y, n_val.z])
        
        n = n / np.linalg.norm(n)

        cross_vec = np.cross(n, target)
        cross_len = np.linalg.norm(cross_vec)
        dot_val = np.dot(n, target)

        if cross_len > 1e-6:
            axis = tuple(cross_vec / cross_len)
            angle = np.degrees(np.arccos(np.clip(dot_val, -1.0, 1.0)))
            solid = solid.rotate((0, 0, 0), axis, angle)
        elif dot_val < 0:
            solid = solid.rotate((0, 0, 0), (1, 0, 0), 180)

        z_min = solid.BoundingBox().zmin
        solid = solid.translate((0, 0, -z_min))
        
        aligned_solids.append(solid)

    return cq.Workplane("XY").newObject(aligned_solids)


def reset_z(part: cq.Workplane) -> cq.Workplane:
    """Set bottom of part to z=0"""
    solids = part.solids().vals()
    aligned_solids = []
    for solid in solids:
        z_min = solid.BoundingBox().zmin
        solid = solid.translate((0, 0, -z_min))
        
        aligned_solids.append(solid)
    
    return cq.Workplane("XY").newObject(aligned_solids)



def trueshape_nesting(parts_data: List[models.PartData], 
                      bin_w: float, 
                      bin_h: float, 
                      tol=2.0, 
                      pad=5.0) -> cq.Workplane:
    """Nests the parts in the parts_data input to a sheet of bin_w x bin_h

    Args:
        parts_data (List[models.PartData]): List of custom data structures (see models module)
        bin_w (float): width of area, or bin, for nesting
        bin_h (float): length of area, or bin, for nesting
        tol (float, optional): Colision sampling frequency. Defaults to 2.0.
        pad (float, optional): Offset between parts. Defaults to 5.0.

    Returns:
        cadquery.Workplane: a cadquery model of the combined nesting for the bin
    """
    # default pad is 5 mm
    # padding determines the spacing between parts and 
    # must always be greater than zero due to physical constraints 

    bin_poly = box(0, 0, bin_w, bin_h)
    placed_polys = [] # Stores padded geometries for collision logic
    results = []

    for p_data in sorted(parts_data, key=lambda d: planar_projection(d.part).area, reverse=True):
        footprint = planar_projection(p_data.part)
        
        x, y, angle, success = place_part(footprint, bin_poly, placed_polys, tol, pad)
        
        if success:
            print(f"placed {os.path.basename(p_data.filename)}")
            # Add the padded version to the collision list
            padded_footprint = footprint.buffer(pad)
            final_geom_padded = translate(rotate(padded_footprint, angle, origin='center'), x, y)
            placed_polys.append(final_geom_padded)
            
            # Translate the ORIGINAL CadQuery object (no padding)
            
            moved_part = p_data.part.rotate((0,0,0), (0,0,1), angle).translate((x, y, 0))
            results.append(moved_part)
            # for more complex sheets this will need an additional call to add
            # nested bins to the full sheet
            
    return results


def model_nest(placed_parts: List[cq.Workplane]) -> cq.Workplane:
    """Combine nested parts into a single CadQuery model for export"""
    result = cq.Workplane("XY")
    for part in placed_parts: 
        aligned_part = reset_z(part)
        result = result.add(aligned_part) 
    return result


def check_z_alignment(nest: cq.Workplane, thickness: float, tolerance = 1e-4) -> bool:
    """Checks if the tops and bottoms of the parts in a nest are aligned within a tolerances"""
    thickness_str = round(thickness / 25.4)

    try:
        solids = get_solids(nest)

        bottom_faces_z = [solid.BoundingBox().zmin for solid in solids]
        top_faces_z = [solid.BoundingBox().zmax for solid in solids]

    except Exception as e:
        print(f"Error verifying z-axis alignment on material thickness: {thickness_str}in: {e}")
        return False

    # check if bottom faces are aligned at z=0
    avg_bottom_z = np.average(bottom_faces_z)
    if not np.isclose(avg_bottom_z, 0, atol=tolerance):
        print(f"Bottom faces may not be aligned on material thickness: {thickness_str}in")
        return False

    # check if top faces are aligned at the expected thickness
    avg_top_z = np.average(top_faces_z)
    if not np.isclose(avg_top_z, thickness, atol=tolerance):
        print(f"Material thicknesses may not be the same on material thickness: {thickness_str}in")
        return False

    return True