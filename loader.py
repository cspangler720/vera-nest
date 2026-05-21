# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from typing import List, Optional, Tuple

import cadquery as cq

import models
from util import get_solids, get_largest_solid


def load_models(model_names: List[str]) -> List[models.PartData]:
    """Loads STEP files and returns custom PartData objects (see models module)."""
    models_are_valid = _validate_model_extensions(model_names)
    if not models_are_valid:
        print("One or more files were found to not be STEP files")
        return []

    parts_data = []
    for file_name in model_names:
        part_data = _load_model(file_name)
        if part_data:
            parts_data.append(part_data)

    return parts_data


def _validate_model_extensions(file_list):
    valid_extensions = {'.step', '.stp'}
    for file in file_list:
        if not any(file.lower().endswith(ext) for ext in valid_extensions):
            return False
    return True


def _load_model(file_name: str) -> Optional[models.PartData]:
    file_path = file_name  # this may need updated logic in the future for pathing
    try:
        part = cq.importers.importStep(file_path)
        thickness, thickness_dir = _identify_thickness(part)
        reoriented_part = _reorient(part, thickness_dir)
        part_data = models.PartData(filename=file_name, part=reoriented_part,
                                    thickness=thickness, footprint=None)
        part_data.footprint = part_data.planar_projection()
        return part_data

    except Exception as e:
        print(f"Failed to load {file_path}: {e}")
        return None


def _identify_thickness(part: cq.Workplane) -> Tuple[float, str]:
    """Determine the thickness and its direction (x, y, or z)."""
    solid = get_solids(part)[0]

    bbox = solid.BoundingBox()
    xlen, ylen, zlen = bbox.xlen, bbox.ylen, bbox.zlen
    dimensions = {"x": xlen, "y": ylen, "z": zlen}

    tolerance = 1e-6
    min_dim = min(dimensions.values())
    thickness_dir = None

    for dir, length in dimensions.items():
        if abs(length - min_dim) < tolerance:
            thickness_dir = dir
            break

    if not thickness_dir:
        raise ValueError("Could not determine thickness direction.")

    return min_dim, thickness_dir


def _is_nested(primary: cq.Solid, secondary: cq.Solid) -> bool:
    primary_bbox = primary.BoundingBox()
    secondary_bbox = secondary.BoundingBox()
    # wip
    pass

def _ideal_orient(part: cq.Workplane, step: float = 10):
    def bbox_area(solid) -> float:
        bb = solid.BoundingBox()
        return bb.xlen * bb.ylen
    
    solids = get_solids(part)

    if len(solids) > 1:
        #sorted_solids = sorted(solids, key=lambda s: (s.BoundingBox().xmin, s.BoundingBox().ymin), reverse=True)
        #result = cq.Workplane()
        #for solid in sorted_solids:
        #    result.add(solid)
        # wip (this is currently throwing parts inside eachother)
        return part #result

    largest_solid = get_largest_solid(part)
    center = largest_solid.Center()
    base = largest_solid.translate((-center.x, -center.y, 0))
    best_shape = base
    best_area = bbox_area(base)

    for angle in range(step, 180 + step, step):
        rotated = base.rotate((0, 0, 0), (0, 0, 1), angle)
        area = bbox_area(rotated)

        if area < best_area:
            best_area = area
            best_shape = rotated
    return cq.Workplane("XY").newObject([best_shape])


def _reorient(part: cq.Workplane, thickness_dir: str) -> cq.Workplane:
    """Reorient the part so the thickness aligns with the Z-axis."""
    if thickness_dir == "x":
        part = part.rotate((0, 0, 0), (0, 1, 0), 90)
    elif thickness_dir == "y":
        part = part.rotate((0, 0, 0), (1, 0, 0), -90)

    part = _ideal_orient(part)

    # verify the part is flat on the XY plane after reorientation
    solids = get_solids(part)
    if solids:
        new_zlen = solids[0].BoundingBox().zlen
        if abs(new_zlen - min(solids[0].BoundingBox().xlen,
                              solids[0].BoundingBox().ylen,
                              new_zlen)) > 1e-6:
            print(f"{part} may not be flat on XY plane after reorientation.")

    return part
