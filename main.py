# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.
#
# This file depends on third-party libraries (including LGPL and Apache 2.0 components).
# Refer to THIRD-PARTY-NOTICES.txt for a full list of dependencies and their licenses.

import os
from typing import List
from tkinter import filedialog

import cadquery as cq
from numpy import cos

import models
import loader
import nesting
import ui
from util import read_json, read_csv


def main():
    # machine parameters are expected to be in mm and degrees
    machine_parameters = read_json(r'.\data\machineParameters.json')["parameters"]

    file_paths = filedialog.askopenfilenames(
        defaultextension=".STEP",
        filetypes=[("STEP Files", "*.STEP *.STP")]
    )

    if not file_paths:
        print("No files selected")
        return

    parts_data: List[models.PartData] = loader.load_models(file_paths)
    if not parts_data:
        print("No parts loaded")
        return

    thickness_groups = nesting.group_thickness(parts_data)

    sheets = read_csv(r'.\data\sheets.csv')
    # probably want to update this to have multiple sheets by thickness and full GUI

    if sheets:
        sheet_width, sheet_height = ui.create_sheet_selection_gui(sheets)
        if sheet_width is None or sheet_height is None:
            print("No valid sheet dimensions selected!")
            return
    else:
        raise ValueError("Sheets not found")

    # assuming all files are in the same folder
    folder_path = os.path.dirname(os.path.abspath(file_paths[0]))
    folder_name = os.path.basename(folder_path)

    machine_pad = machine_parameters["KERF"] + machine_parameters["TOLERANCE"]
    for thickness, parts_in_group in thickness_groups.items():
        thickness_str = f"{thickness / 25.4:.4f}".replace(".", "p")
        print(f"\nNest for {thickness_str}in:")
        pad = 0.5 * (machine_pad + thickness * cos(machine_parameters["TAPER_ANGLE"] * 0.01745))
        print(f"The pad is {pad / 25.4:.4f}-in")

        placed_parts = nesting.nest(parts_in_group,
                                    sheet_width,
                                    sheet_height,
                                    tolerance=2.0,
                                    pad=pad)

        if not placed_parts:
            print(f"No parts placed for thickness {thickness_str}in, skipping export")
            continue

        output_filename = f"{folder_name}_{thickness_str}in.STEP"
        output_path = os.path.join(folder_path, output_filename)

        nested_model = nesting.model_nest(placed_parts)
        _ = nesting.check_z_alignment(nested_model, thickness)
        # alignment checker will print information if the model is not aligned
        # we do not need the return bool from it though

        get_yield(nested_model, sheet_width, sheet_height)
        cq.exporters.export(nested_model, output_path, exportType="STEP")
        print(f"Exported: {output_path}")


def get_yield(nested_model: cq.Workplane, sheet_width: float, sheet_height: float):
    # bounding box of the full nest footprint
    all_solids = nested_model.solids().vals()
    if not all_solids:
        print("No solids found for yield calculation")
        return

    xs = [s.BoundingBox().xmin for s in all_solids] + [s.BoundingBox().xmax for s in all_solids]
    ys = [s.BoundingBox().ymin for s in all_solids] + [s.BoundingBox().ymax for s in all_solids]
    nested_area = (max(xs) - min(xs)) * (max(ys) - min(ys))

    # sum the bottom face areas (faces at z ≈ 0) as part footprint area
    z_floor = min(s.BoundingBox().zmin for s in all_solids)
    part_area = sum(
        f.Area() for solid in all_solids
        for f in solid.Faces()
        if abs(f.Center().z - z_floor) < 1e-3
    )

    sheet_area = sheet_width * sheet_height
    nest_yield = part_area / (nested_area + 0.0001)
    sheet_yield = part_area / sheet_area
    rect_yield = (sheet_area - nested_area) / sheet_area
    print(f"Nest yield: {nest_yield:.3f}\nSheet yield: {sheet_yield:.3f}\nRectangular yield: {rect_yield:.3f}")


if __name__ == "__main__":
    main()