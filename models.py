# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from dataclasses import dataclass
from typing import Sequence

import cadquery as cq
from shapely.ops import unary_union
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.affinity import rotate

from nfp import nfp as compute_nfp, nfp_inner, place, translate_to
from util import get_largest_solid

@dataclass
class PartData:
    """Captures the filename, cadquery reference (part), nesting profile (footprint), and a thickness value of a part"""
    # this allows the loader module to create a list of part data's
    filename: str
    part: cq.Workplane
    footprint: Polygon
    thickness: float

    def planar_projection(self): # probably should wrap into the initialization
        solid = get_largest_solid(self.part)
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


@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    height: float


class Sheet:
    """Represents a sheet metal"""
    # ideally this can be used for custom sheets
    # the plan is to have a user-json file containing the available sheets and remnants
    # the json would contain data to initialize these objects to a dictionary

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


class Job:
    """
    Iteratively nest a list of Shapely polygons into a bin polygon.
    Use by initializing a jobxyz = Job(bin_polygon) and its results = jobxyz.nest(parts)
    """

    def __init__(self, bin_poly: Polygon, rotation_steps: int = 4):
        """
        Parameters
        bin_poly (shapely.Polygon): container polygon (must be simple, no holes)
        rotation_steps (int): number of rotation candidates to try (evenly spaced 0-360 degrees)
        """
        self.bin_poly = bin_poly
        self.rotation_steps = rotation_steps
        self._placed: list[Polygon] = []   # placed pieces (in bin coordinates)

    def _valid_region(self, piece: Polygon) -> Polygon | MultiPolygon | None:
        """
        Compute the valid placement region for `piece`:
        IFP(bin, piece)  minus  union of NFP(placed_i, piece) for each placed piece.
        """
        ifp = nfp_inner(self.bin_poly, piece)
        if ifp is None or ifp.is_empty:
            return None

        forbidden = []
        for placed in self._placed:
            outer_nfp = compute_nfp(placed, piece)
            if outer_nfp is not None and not outer_nfp.is_empty:
                forbidden.append(outer_nfp)

        if forbidden:
            forbidden_union = unary_union(forbidden)
            valid = ifp.difference(forbidden_union)
        else:
            valid = ifp

        return valid if not valid.is_empty else None

    def _try_place(self, piece: Polygon) -> tuple[Polygon, tuple[float, float]] | None:
        """
        Try multiple rotations; return (placed_polygon, (cx, cy)) for the
        best (bottom-left) placement found, or None.
        """
        angles = [i * 360.0 / self.rotation_steps for i in range(self.rotation_steps)]
        best = None

        for angle in angles:
            rotated = rotate(piece, angle, origin='centroid')
            valid = self._valid_region(rotated)
            if valid is None:
                continue
            pt = place(valid, rotated)
            if pt is None:
                continue
            placed = translate_to(rotated, pt[0], pt[1])
            # Score: (y, x) of centroid — lower is better
            score = (round(pt[1], 4), round(pt[0], 4))
            if best is None or score < best[0]:
                best = (score, placed, pt)

        if best is None:
            return None
        return best[1], best[2]

    def nest(self, pieces: Sequence[Polygon]) -> list[dict]:
        """
        Nest all pieces into the bin.  Pieces are attempted in order.

        Returns list of placement result dicts.
        """
        results = []
        self._placed = []

        for i, piece in enumerate(pieces):
            result = self._try_place(piece)
            if result is not None:
                placed_poly, placement = result
                self._placed.append(placed_poly)
                results.append({
                    "piece_index": i,
                    "polygon": placed_poly,
                    "placement": placement,
                    "placed": True,
                })
            else:
                results.append({
                    "piece_index": i,
                    "polygon": piece,
                    "placement": None,
                    "placed": False,
                })

        return results

    @property
    def utilization(self) -> float:
        """Area utilization ratio: sum(placed areas) / bin area."""
        if not self._placed:
            return 0.0
        placed_area = sum(p.area for p in self._placed)
        return placed_area / self.bin_poly.area
    