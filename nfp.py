# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

"""This module was designed by me on paper and prompted into ClaudeAI for the math."""

from typing import Tuple, Sequence

import numpy as np
import pyclipper as clip

from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from shapely.affinity import translate

_SCALE = 1000000
_TOLERANCE = 1e-6


def _shapely_to_clipper(poly: Polygon, scale: int = _SCALE) -> list[list[list[int]]]:
    """Module input conversion"""
    exterior_coords_scaled = _scale_points(poly.exterior.coords[:-1])
    # added [:-1] to remove duplicate point
    holes_coords_scaled = [_scale_points(list(h.coords)[:-1]) for h in poly.interiors]
    return [exterior_coords_scaled] + holes_coords_scaled

def _scale_points(coords: Sequence[Tuple[float, float]],
                  scale: int = _SCALE) -> list[list[int]]:
    return [[int(x * scale), int(y * scale)] for x, y in coords]

def _clipper_to_shapely(paths: list, scale: int = _SCALE) -> Polygon | MultiPolygon:
    """Module output conversion"""
    polys = []
    for path in paths:
        coords = [(x / scale, y / scale) for x, y in path]
        if len(coords) >= 3:
            polys.append(Polygon(coords))
    if not polys:
        return None
    return unary_union(polys)

def _exterior_coords(poly: Polygon) -> np.ndarray:
    # added [:-1] to remove duplicate point
    return np.array(poly.exterior.coords)[:-1]


def _poly_centroid(poly: Polygon) -> Tuple[float, float]:
    return poly.centroid.x, poly.centroid.y


def _center_poly(poly: Polygon) -> Polygon:
    # uses shapely polygon class methods
    # may not work for a multipolygon
    x_0, y_0 = _poly_centroid(poly)
    return translate(poly, -x_0, -y_0)


def _reflect(poly: Polygon) -> Polygon:
    """Reflect a polygon through the origin."""
    coords = _exterior_coords(poly)
    reflected = [(-x, -y) for x, y in coords]
    return Polygon(reflected)


def minkowski_sum(poly_A: Polygon, poly_B: Polygon) -> Polygon | MultiPolygon:
    perimiter_a = _exterior_coords(poly_A).tolist()
    perimiter_b = _exterior_coords(poly_B).tolist()

    perimiter_a_i = [[int(x * _SCALE), int(y * _SCALE)] for x, y in perimiter_a]
    perimiter_b_i = [[int(x * _SCALE), int(y * _SCALE)] for x, y in perimiter_b]
    # pyclipper MinkowskiSum expects integer paths
    solution = clip.MinkowskiSum(perimiter_b_i, perimiter_a_i, True)
    return _clipper_to_shapely(solution)


def minkowski_diff(poly_A: Polygon, poly_B: Polygon) -> Polygon | MultiPolygon:
    return minkowski_sum(poly_A, _reflect(poly_B))


def nfp(sun: Polygon, planet: Polygon) -> Polygon | MultiPolygon:
    """Orbiting computation of the planet polygon about the sun polygon

    inspired by https://nestprofessor.com/articles/An%20improved%20method%20for%20calculating%20the%20no-fit%20polygon(Automatic%20nesting%20software).pdf
    Args:
        sun (Polygon): existing polygons in the nest which are already placed
        planet (Polygon): polygons to be placed

    Returns:
        Polygon | MultiPolygon: NFP (same item but my IDE yells at me if I use the type hints for just Polygon)
    """
    # NFP = Minkowski sum of sun with the reflection of planet
    return minkowski_sum(sun, _reflect(planet))


def ifp(bin_poly: Polygon, part: Polygon) -> Polygon | MultiPolygon:
    """Inner fit polygon"""
    part_centered_origin = _center_poly(part)
    return minkowski_diff(bin_poly, part_centered_origin)


# alias for external callers
nfp_inner = ifp


def place(valid_region: Polygon | MultiPolygon, part: Polygon) -> Tuple[float, float]:
    """Place in desired placement region
    Currently works on placing in the bottom left corner.
    valid_region = IFP - NFP
    """ # future implementation could add an area minimizing placement
    # this is not the current approach as a genetic algorithm will likely
    # be used instead of the former at the nesting inputs level
    if valid_region is None or valid_region.is_empty:
        print(f"No valid region for part {part}")
        return None # may just be able to do if not valid_region
    candidates = []

    if isinstance(valid_region, Polygon):
        geometries = [valid_region]
    else:
        geometries = list(valid_region.geoms)

    for geo in geometries:
        for coord in geo.exterior.coords:
            candidates.append(coord)

    if not candidates:
        return None

    # Bottom-left y priority
    candidates.sort(key=lambda p: (round(p[1], 6), round(p[0], 6)))
    for x_0, y_0 in candidates:
        test_point = Point(x_0, y_0)
        if valid_region.contains(test_point) or valid_region.boundary.distance(test_point) < _TOLERANCE:
            return (x_0, y_0)


def translate_to(poly: Polygon, target_x: float, target_y: float) -> Polygon:
    """Translate poly so its centroid lands at (target_x, target_y)."""
    cx, cy = _poly_centroid(poly)
    return translate(poly, target_x - cx, target_y - cy)


def bounding_box_polygon(poly: Polygon) -> Polygon:
    """Return the axis-aligned bounding box as a Shapely Polygon."""
    minx, miny, maxx, maxy = poly.bounds
    return Polygon([
        (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)
    ])


def pack_efficiency(bin_poly: Polygon, placed: list[Polygon]) -> dict:
    """Return packing statistics."""
    bin_area = bin_poly.area
    packed_area = sum(p.area for p in placed)
    waste = bin_area - packed_area
    return {
        "bin_area": bin_area,
        "packed_area": packed_area,
        "waste_area": waste,
        "utilization_pct": 100.0 * packed_area / bin_area if bin_area else 0.0,
        "n_placed": len(placed),
    }


def convex_hull_nfp(fixed: Polygon, orbiting: Polygon) -> Polygon | MultiPolygon | None:
    """
    Faster approximate NFP using convex hulls of both polygons.
    Useful as a quick upper-bound / feasibility check.
    """
    return nfp(fixed.convex_hull, orbiting.convex_hull)