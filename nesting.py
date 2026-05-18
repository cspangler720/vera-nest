# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from typing import List, Dict

import numpy as np
import cadquery as cq

import models

MAGIC_VALUE = -1000000


def group_thickness(parts_data: List[models.PartData]) -> Dict[float, List[models.PartData]]:
    thickness_groups: Dict[float, List[models.PartData]] = {}
    for part_data in parts_data:
        thickness = round(part_data.thickness, 4)
        if thickness not in thickness_groups:
            thickness_groups[thickness] = []
        thickness_groups[thickness].append(part_data)
    return thickness_groups


def _sort(parts_data: List[models.PartData]) -> List[cq.Workplane]:
    sorted_parts_data = sorted(parts_data, key=lambda p: p.part.val().BoundingBox().xlen, reverse=True)
    return [p.part for p in sorted_parts_data]


def _get_solids(parts: cq.Workplane, tol: float=0.1):
    final_solids = []
    solid_parts = parts.solids().all()
    for part in solid_parts:
        try: 
            solids = part.solids
        except Exception:
            print(f"No solids found in {part}")
            continue

        for _, solid in enumerate(solids):
            merged = False
            for j, existing in enumerate(final_solids):
                if _is_nested(solid, existing, tol):
                    final_solids[j] = existing.union(solid)
                    merged = True
                    break
            if not merged:
                final_solids.append(solid)
    return final_solids
	

def center_distance(A, B):
	return np.sqrt((A.x - B.x)**2 + (A.y - B.y)**2)
	

def _is_nested(solid1, solid2, tol):
	c1 = solid1.center
	c2 = solid2.center
	if center_distance(c1, c2) < tol:
		return True
	return False

def sort_row(parts):
    order = sorted(parts, key=lambda part: part.val().BoundingBox().xlen, reverse=True)
    longest = order[0]
    for partA, partB, partC in zip(order, order[1:], order[2:]):
        long_edgeA = partA.val().BoundingBox().xlen
        long_edgeB = partB.val().BoundingBox().xlen
        short_edgeB = partB.val().BoundingBox().ylen
        long_edgeC = partC.val().BoundingBox().xlen
        short_edgeC = partC.val().BoundingBox().ylen
        return long_edgeA, long_edgeB, long_edgeC, short_edgeB, short_edgeC, longest
    # WIP 
    # sort for stack packing
    return 

    

def check_x(x_prior, y_lower, y_upper, bin_x, bin_y, pad, boarder, part):
	if x_prior + pad + part.val().BoundingBox().xlen <= bin_x - boarder:
		# update Y_lower
		return y_upper + pad
	return y_lower


def check_y(y_upper, bin_y, pad, boarder, part):
	if y_upper + pad + part.val().BoundingBox().ylen <= bin_y - boarder: 
		return False
	return True # can place


def check_stack(y_upper, x_prior, pad, part):
	if y_upper <= part.val().BoundingBox().ylen + pad:
		return True
	return False # x_prior is passed here logic to be added 
                 # later with the custom sort
	

def stack_y(y_prior, pad, part):
	return y_prior + pad + part.val().BoundingBox().ylen
	

# x_prior isnt the x-value of the prior but the right edge of the part 
def position(y_lower, y_upper, x_prior, y_prior, pad, boarder, bin_x, bin_y, part):
	if check_y(y_upper, bin_y, pad, boarder, part):
		return MAGIC_VALUE, MAGIC_VALUE, MAGIC_VALUE, MAGIC_VALUE, MAGIC_VALUE # need different returns
	
	# bottom-left corner coordinates
	target_x, target_y = x_prior, y_prior + pad
	can_stack = check_stack(y_upper, x_prior, pad, part)
	if can_stack:
		target_y = stack_y(y_prior, pad, part)
	target_x = x_prior + pad
	target_y = check_x(x_prior, y_lower, y_upper, bin_x, bin_y, pad, boarder, part)
	return target_x, target_y, y_upper, target_x + part.val().BoundingBox().xlen, y_prior
	

def place(target_x, target_y, part):
	return part.translate((target_x, target_y, 0))
	

def nest(bin_x, bin_y, boarder, pad, parts_data):
    parts = _sort(parts_data)
    first_part = parts[0]
    parts.pop(0)
    y_lower = boarder
    x_prior = boarder
    y_upper = first_part.val().BoundingBox().ylen
    # make sure result is of type workplane
    result = first_part.translate((boarder, boarder, 0))
    x_prior = first_part.val().BoundingBox().xlen + boarder
    y_prior = first_part.val().BoundingBox().ylen
    target_x = x_prior
    target_y = y_lower 
    result.add(place(target_x, target_y, parts[0]))
    parts.pop(0)
    if not parts:
        return result
    for part in parts:
        target_x, target_y, y_upper, x_prior, y_prior = position(y_lower, y_upper, x_prior, y_prior, pad, boarder, bin_x, bin_y, part)
        result.add(place(target_x, target_y, part))
    return result
  
def new_nest(bin_x, bin_y, boarder, pad, parts_data):
    parts = _sort(parts_data)
    first_part = parts.pop(0)
    
    y_lower = boarder
    x_prior = boarder
    y_prior = boarder

    result = first_part.translate((boarder, boarder, 0))
    x_prior = first_part.val().BoundingBox().xlen + boarder
    y_upper = first_part.val().BoundingBox().ylen + boarder
    y_prior = first_part.val().BoundingBox().ylen + boarder

    if not parts:
        return result

    for part in parts:
        target_x, target_y, y_upper, x_prior, y_prior = position(
            y_lower, y_upper, x_prior, y_prior, pad, boarder, bin_x, bin_y, part
        )
        if target_x == MAGIC_VALUE: # position signals failure
            continue
        result.add(place(target_x, target_y, part))

    return result


def normalize_axes(shape):
    inertia = shape.Inertia()
    com = inertia.com
    moments = inertia.principal_moments 
    axes = inertia.principal_axes       
    sorted_pairs = sorted(zip(moments, axes), key=lambda x: x[0])
    long_v = sorted_pairs[0][1]   # Target: X
    mid_v  = sorted_pairs[1][1]   # Target: Y
    short_v = sorted_pairs[2][1]  # Target: Z
    rot_matrix = cq.Matrix([
	    [long_v.x, mid_v.x, short_v.x, 0],
	    [long_v.y, mid_v.y, short_v.y, 0],
	    [long_v.z, mid_v.z, short_v.z, 0],
	    [0, 0, 0, 1]
	])
    normalized = shape.translate(com.multiply(-1)).transformShape(rot_matrix.inverse())
    z_min = normalized.BoundingBox().zmin
    return normalized.translate(cq.Vector(0, 0, -z_min))
    

def model_nest(placed_parts: List[cq.Workplane]) -> cq.Workplane:
    """Combine nested parts into a single CadQuery model for export"""
    result = cq.Workplane("XY")
    for part in placed_parts:
        # Ensure the part is a Workplane with solids
        if not hasattr(part, 'solids'):
            raise ValueError(f"Expected a Workplane with solids, got {type(part)}")
        aligned_part = _reset_z(part)  # part is expected to be a solid
        result = result.add(aligned_part)
    return result


def _reset_z(solids) -> cq.Workplane:
    """Set bottom of part to z=0"""
    aligned_solids = []
    for solid in solids:
        z_min = solid.BoundingBox().zmin
        solid = solid.translate((0, 0, -z_min))
        
        aligned_solids.append(solid)
    
    return cq.Workplane("XY").newObject(aligned_solids)


def check_z_alignment(nest: cq.Workplane, thickness: float, thickness_str: str, tolerance = 1e-4) -> bool:
    """Checks if the tops and bottoms of the parts in a nest are aligned within a tolerances"""
    try:
        solids = _get_solids(nest)
        bottom_faces_z = [solid.BoundingBox().zmin for solid in solids]
        top_faces_z = [solid.BoundingBox().zmax for solid in solids]
    except Exception as e:
        print(f"Error verifying z-axis alignment on material thickness: {thickness_str}: {e}")
        return False

    # check if bottom faces are aligned at z=0
    avg_bottom_z = np.average(bottom_faces_z)
    if not np.isclose(avg_bottom_z, 0, atol=tolerance):
        print(f"Bottom faces may not be aligned on material thickness: {thickness_str}")
        return False

    # check if top faces are aligned at the expected thickness
    avg_top_z = np.average(top_faces_z)
    if not np.isclose(avg_top_z, thickness, atol=tolerance):
        print(f"Material thicknesses may not be the same on material thickness: {thickness_str}")
        return False

    return True
