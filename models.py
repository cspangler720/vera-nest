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
    """Captures the filename, cadquery reference to the part and a and thickness value for the part"""
    filename: str
    part: cq.Workplane
    thickness: float
