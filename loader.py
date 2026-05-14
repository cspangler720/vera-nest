# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from typing import List, Optional, Tuple

import cadquery as cq

import models
from util import get_solids

def load_models(model_names: List[str]) -> List[models.PartData]:
    """Loads STEP files and return custom PartData objects (see models module)."""
    models_are_valid = validate_model_extensions(model_names)
    if not models_are_valid:
        print("One or more files were found to not be STEP files")
        return []

    parts_data = []
    for file_name in model_names:
        part_data = load_model(file_name)
        if part_data:
            parts_data.append(part_data)

    return parts_data


def validate_model_extensions(file_list):
    valid_extensions = {'.step', '.stp'}
    for file in file_list:
        if not any(file.lower().endswith(ext) for ext in valid_extensions):
            return False
    return True


def load_model(file_name: str) -> Optional[models.PartData]:
    file_path = file_name # this may need updated logic in the future for pathing
    try:
        part = cq.importers.importStep(file_path)
        thickness, thickness_dir = identify_thickness(part)
        reoriented_part = reorient(part, thickness_dir)
        part_data = models.PartData(filename=file_name, part=reoriented_part,
            thickness=thickness, footprint=None) 
        part_data.footprint = part_data.planar_projection()
        return part_data
    
    except Exception as e:
        print(f"Failed to load {file_path}: {e}")
        return None


def identify_thickness(part: cq.Workplane) -> Tuple[float, str]:
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


def reorient(part: cq.Workplane, thickness_dir: str) -> cq.Workplane:
    """Reorient the part so the thickness aligns with the Z-axis."""
    if thickness_dir == "x":
        part = part.rotate((0, 0, 0), (0, 1, 0), 90)
    elif thickness_dir == "y":
        part = part.rotate((0, 0, 0), (1, 0, 0), -90)

    new_bbox = part.val().BoundingBox()
    if abs(new_bbox.zlen - part.val().BoundingBox().zlen) > 1e-6:
        print(f"{part} may not be flat on XY plane after reorientation.")

    return part