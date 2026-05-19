# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from typing import List, Dict, Tuple, Optional

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


def _get_solids(parts: cq.Workplane, tol: float = 0.1):
    """Extract and merge nested solids from a Workplane."""
    final_solids = []
    solid_parts = parts.solids().all()
    for part in solid_parts:
        # .val() gives us the underlying Shape/Solid
        solid = part.val()
        if solid is None:
            print(f"No solid found in part: {part}")
            continue

        merged = False
        for j, existing in enumerate(final_solids):
            if _is_nested(solid, existing, tol):
                final_solids[j] = existing.fuse(solid)  # use fuse for OCC shapes
                merged = True
                break
        if not merged:
            final_solids.append(solid)

    return final_solids


def center_distance(A, B) -> float:
    return np.sqrt((A.x - B.x) ** 2 + (A.y - B.y) ** 2)


def _is_nested(solid1, solid2, tol: float) -> bool:
    c1 = solid1.Center()
    c2 = solid2.Center()
    if center_distance(c1, c2) < tol:
        return True
    return False


def sort_row(parts: List[cq.Workplane]):
    """Sort parts for row-based stack packing. WIP."""
    order = sorted(parts, key=lambda part: part.val().BoundingBox().xlen, reverse=True)
    longest = order[0]

    result = []
    # Iterate all triples — do NOT return inside the loop
    for partA, partB, partC in zip(order, order[1:], order[2:]):
        long_edgeA = partA.val().BoundingBox().xlen
        long_edgeB = partB.val().BoundingBox().xlen
        short_edgeB = partB.val().BoundingBox().ylen
        long_edgeC = partC.val().BoundingBox().xlen
        short_edgeC = partC.val().BoundingBox().ylen
        result.append((long_edgeA, long_edgeB, long_edgeC, short_edgeB, short_edgeC))

    # WIP: use result + longest to drive stack packing order
    return order


def check_x(x_prior: float, y_lower: float, y_upper: float,
            bin_x: float, bin_y: float, pad: float, border: float,
            part: cq.Workplane) -> Tuple[float, float]:
    """
    Check whether the part fits to the right of x_prior.
    Returns (new_x, new_y): the bottom-left corner to place the part at.
    If it doesn't fit horizontally, wrap to a new row starting at y_upper.
    """
    part_xlen = part.val().BoundingBox().xlen
    if x_prior + pad + part_xlen <= bin_x - border:
        # Fits in the current row
        return x_prior + pad, y_lower
    else:
        # Start a new row
        return border, y_upper + pad


def check_y(y_upper: float, bin_y: float, pad: float, border: float,
            part: cq.Workplane) -> bool:
    """Returns True if the part fits vertically (there is still room), False if it does not."""
    return y_upper + pad + part.val().BoundingBox().ylen <= bin_y - border


def check_stack(y_upper: float, x_prior: float, pad: float,
                part: cq.Workplane) -> bool:
    """
    Returns True if we can stack the part on top of the current row
    (i.e. the part's height fits within y_upper).
    """
    return part.val().BoundingBox().ylen + pad <= y_upper


def stack_y(y_prior: float, pad: float, part: cq.Workplane) -> float:
    return y_prior + pad + part.val().BoundingBox().ylen


def position(
    y_lower: float, y_upper: float, x_prior: float, y_prior: float,
    pad: float, border: float, bin_x: float, bin_y: float,
    part: cq.Workplane
) -> Tuple[float, float, float, float, float]:
    """
    Compute placement coordinates for a part.

    Returns:
        (target_x, target_y, new_y_upper, new_x_prior, new_y_prior)
        All values are MAGIC_VALUE if the part cannot be placed.
    """
    FAIL = (MAGIC_VALUE,) * 5

    if not check_y(y_upper, bin_y, pad, border, part):
        return FAIL

    target_x, target_y = check_x(x_prior, y_lower, y_upper, bin_x, bin_y, pad, border, part)

    # If check_x wrapped to a new row, re-validate vertical fit from the new y
    if target_x == border and target_y == y_upper + pad:
        new_y_upper = target_y + part.val().BoundingBox().ylen
        new_y_prior = target_y
        new_x_prior = border + part.val().BoundingBox().xlen
        return target_x, target_y, new_y_upper, new_x_prior, new_y_prior

    # Same row placement
    new_x_prior = target_x + part.val().BoundingBox().xlen
    new_y_prior = target_y
    new_y_upper = max(y_upper, target_y + part.val().BoundingBox().ylen)
    return target_x, target_y, new_y_upper, new_x_prior, new_y_prior


def place(target_x: float, target_y: float, part: cq.Workplane) -> cq.Workplane:
    return part.translate((target_x, target_y, 0))


def nest(bin_x: float, bin_y: float, border: float, pad: float,
         parts_data: List[models.PartData]) -> Optional[cq.Workplane]:
    """
    Nest parts into a bin of size (bin_x, bin_y).
    Returns a Workplane containing all placed parts, or None if no parts provided.
    """
    parts = _sort(parts_data)
    if not parts:
        return None

    # Place the first (largest) part at the border
    first_part = parts.pop(0)
    y_lower = border
    x_prior = border + first_part.val().BoundingBox().xlen
    y_prior = border
    y_upper = border + first_part.val().BoundingBox().ylen

    result = first_part.translate((border, border, 0))

    if not parts:
        return result

    for part in parts:
        target_x, target_y, y_upper, x_prior, y_prior = position(
            y_lower, y_upper, x_prior, y_prior, pad, border, bin_x, bin_y, part
        )
        if target_x == MAGIC_VALUE:
            print(f"Warning: part {part} could not be placed — bin may be full.")
            continue
        result = result.add(place(target_x, target_y, part))

    return result


def normalize_axes(shape):
    inertia = shape.Inertia()
    com = inertia.com
    moments = inertia.principal_moments
    axes = inertia.principal_axes
    sorted_pairs = sorted(zip(moments, axes), key=lambda x: x[0])
    long_v = sorted_pairs[0][1]    # Target: X
    mid_v = sorted_pairs[1][1]     # Target: Y
    short_v = sorted_pairs[2][1]   # Target: Z
    rot_matrix = cq.Matrix([
        [long_v.x, mid_v.x, short_v.x, 0],
        [long_v.y, mid_v.y, short_v.y, 0],
        [long_v.z, mid_v.z, short_v.z, 0],
        [0, 0, 0, 1]
    ])
    normalized = shape.translate(com.multiply(-1)).transformShape(rot_matrix.inverse())
    z_min = normalized.BoundingBox().zmin
    return normalized.translate(cq.Vector(0, 0, -z_min))


def model_nest(placed_parts: cq.Workplane) -> cq.Workplane:
    """
    Reset all solids in the nested Workplane to z=0 and return a clean Workplane.

    nest() returns a single cq.Workplane whose context stack holds all placed
    solids.  Iterating it directly yields raw Solid objects (via .vals()), so
    we extract them through .solids().vals() which is the documented CadQuery
    way to get a typed list of Solid shapes from a Workplane.
    """
    if not isinstance(placed_parts, cq.Workplane):
        raise ValueError(f"model_nest expects a cq.Workplane, got {type(placed_parts)}")

    result = _reset_z(placed_parts)
    print(result.vals())
    return result


def _reset_z(workplane: cq.Workplane) -> cq.Workplane:
    """Translate every solid in a Workplane so its bottom face sits at z=0."""
    # .solids().vals() returns List[cq.occ_impl.shapes.Solid] — the correct
    # CadQuery API for extracting typed solid shapes from a Workplane.
    aligned_solids = []
    for solid in workplane.solids().vals():
        z_min = solid.BoundingBox().zmin
        aligned_solids.append(solid.translate((0, 0, -z_min)))
    return cq.Workplane("XY").newObject(aligned_solids)


def check_z_alignment(nest: cq.Workplane, thickness: float,
                      thickness_str: str, tolerance: float = 1e-4) -> bool:
    """Check if tops and bottoms of all parts in a nest are aligned within tolerance."""
    try:
        solids = _get_solids(nest)
        bottom_faces_z = [solid.BoundingBox().zmin for solid in solids]
        top_faces_z = [solid.BoundingBox().zmax for solid in solids]
    except Exception as e:
        print(f"Error verifying z-axis alignment on material thickness {thickness_str}: {e}")
        return False

    avg_bottom_z = np.average(bottom_faces_z)
    if not np.isclose(avg_bottom_z, 0, atol=tolerance):
        print(f"Bottom faces may not be aligned on material thickness: {thickness_str}")
        return False

    avg_top_z = np.average(top_faces_z)
    if not np.isclose(avg_top_z, thickness, atol=tolerance):
        print(f"Material thicknesses may not be the same on material thickness: {thickness_str}")
        return False

    return True
