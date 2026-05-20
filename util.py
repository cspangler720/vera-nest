# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

import json
import csv
import os
from typing import Dict, List

import cadquery as cq


def get_solids(part: cq.Workplane) -> cq.Workplane:
    try: 
        solids = list(part.solids())  # body may contain more than one solid
    except ValueError:
        print(f"No solids found in {part}")
    return solids


def read_json(file_path: str) -> Dict:
    if not os.path.exists(file_path):
        print(f"JSON file not found: {file_path}")
        return 

    with open(file_path, 'r') as file:
        dictionary = json.load(file)
    return dictionary


def read_csv(file_path: str) -> List[dict]:
    rows = []
    if not os.path.exists(file_path):
        print(f"CSV file not found: {file_path}")
        return rows
    with open(file_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "name": row["name"],
                "width": float(row["width"]),
                "height": float(row["height"]),
            })
    return rows