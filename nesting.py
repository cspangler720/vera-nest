# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from typing import List, Tuple, Dict

import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, box
from shapely.affinity import translate, rotate

import models
from util import get_solids

ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]


def group_thickness(parts_data: List[models.PartData]) -> Dict[float, List[models.PartData]]:
    thickness_groups: Dict[float, List[models.PartData]] = {}
    for part_data in parts_data:
        thickness = round(part_data.thickness, 4)
        if thickness not in thickness_groups:
            thickness_groups[thickness] = []
        thickness_groups[thickness].append(part_data)
    return thickness_groups


def _bounding_box(solid) -> Tuple[float, float]:
    bbox = solid.BoundingBox()
    return bbox.xlen, bbox.ylen


def _area(part_data: models.PartData) -> float:
    width, height = _bounding_box(get_solids(part_data.part)[0])
    return width * height


# this could be updated to sort based on some sort of ml algorithm
def _sort(parts_data: List[models.PartData]) -> List[models.PartData]:
    return sorted(parts_data, key=_area, reverse=True)


def _search_candidates(bin_polygon: Polygon, placed_parts: List[Polygon],
                       tolerance: float) -> List[Tuple[float, float]]:
    candidates = set()
    bin_minx, bin_miny, bin_maxx, bin_maxy = bin_polygon.bounds

    # Add bin corners
    candidates.update([
        (bin_minx, bin_miny),
        (bin_maxx, bin_miny),
        (bin_minx, bin_maxy),
        (bin_maxx, bin_maxy),
    ])

    # Add points around placed parts
    for placed in placed_parts:
        p_minx, p_miny, p_maxx, p_maxy = placed.bounds
        for x in np.arange(p_minx, p_maxx + tolerance, tolerance):
            candidates.add((x, p_miny - tolerance))
            candidates.add((x, p_maxy + tolerance))
        for y in np.arange(p_miny, p_maxy + tolerance, tolerance):
            candidates.add((p_minx - tolerance, y))
            candidates.add((p_maxx + tolerance, y))

    # Add points along bin edges
    for x in np.arange(bin_minx, bin_maxx + tolerance, tolerance):
        candidates.add((x, bin_miny))
        candidates.add((x, bin_maxy))
    for y in np.arange(bin_miny, bin_maxy + tolerance, tolerance):
        candidates.add((bin_minx, y))
        candidates.add((bin_maxx, y))

    return sorted(candidates, key=lambda p: (p[1], p[0]))


def _place_part(part_polygon: Polygon, bin_polygon: Polygon,
                placed_parts: List[Polygon], tolerance: float,
                pad: float) -> Tuple[float, float, float, bool]:
    padded_part = part_polygon.buffer(pad)
    rotated_parts = [rotate(padded_part, angle, origin="center") for angle in ANGLES]
    candidates = _search_candidates(bin_polygon, placed_parts, tolerance)

    for angle, rotated_part in zip(ANGLES, rotated_parts):
        p_minx, p_miny, _, _ = rotated_part.bounds
        for x, y in candidates:
            xoff = x - p_minx
            yoff = y - p_miny
            candidate = translate(rotated_part, xoff=xoff, yoff=yoff)

            if not bin_polygon.covers(candidate):
                continue
            if any(candidate.intersects(existing) for existing in placed_parts):
                continue

            return (xoff, yoff, angle, True)

    return (0.0, 0.0, 0.0, False)


def nest(parts_data: List[models.PartData], bin_w: float, bin_h: float,
         tolerance: float = 2.0, pad: float = 0.5) -> List[cq.Workplane]:
    bin_poly = box(0, 0, bin_w, bin_h)
    placed_polys: List[Polygon] = []  # polygons padded for kerf and cut tolerance
    result: List[cq.Workplane] = []   # final models with appropriate translation and rotation

    sorted_parts = _sort(parts_data)

    for part_data in sorted_parts:
        part_polygon = part_data.footprint
        x, y, angle, success = _place_part(part_polygon, bin_poly, placed_polys,
                                            tolerance, pad)
        if not success:
            print(f"Could not place: {part_data.filename}")
            continue

        padded_part = part_polygon.buffer(pad)
        rotated_padded = rotate(padded_part, angle, origin="center")
        final_padded = translate(rotated_padded, xoff=x, yoff=y)
        placed_polys.append(final_padded)

        placed_part = part_data.part.rotate((0, 0, 0), (0, 0, 1), angle).translate((x, y, 0))
        result.append(placed_part)

    return result


def model_nest(placed_parts: List[cq.Workplane]) -> cq.Workplane:
    """Combine nested parts into a single CadQuery model for export"""
    result = cq.Workplane("XY")
    for part in placed_parts:
        aligned_part = _reset_z(part)
        result = result.add(aligned_part)
    return result


def _reset_z(part: cq.Workplane) -> cq.Workplane:
    """Set bottom of part to z=0"""
    solids = part.solids().vals()
    aligned_solids = []
    for solid in solids:
        z_min = solid.BoundingBox().zmin
        solid = solid.translate((0, 0, -z_min))
        aligned_solids.append(solid)
    return cq.Workplane("XY").newObject(aligned_solids)


def check_z_alignment(nest: cq.Workplane, thickness: float, tolerance=1e-4) -> bool:
    """Checks if the tops and bottoms of the parts in a nest are aligned within a tolerance"""
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
