# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

from dataclasses import dataclass

import cadquery as cq

@dataclass
class PartData:
    """Captures the filename, cadquery reference, and thickness value of a part"""
    # this allows the loader module to create a list of part data's 
    filename: str
    part: cq.Workplane
    thickness: float


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