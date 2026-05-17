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
        print(f"\nNest for {thickness_str}:")
        pad = 0.5 * (machine_pad + thickness * cos(machine_parameters["TAPER_ANGLE"] * 0.01744))
        print(f"The pad is {pad/25.4:.4f}-in")

        placed_parts = nesting.nest(parts_in_group, 
                                    sheet_width,
                                    sheet_height, 
                                    tolerance=2.0, 
                                    pad=pad)

        output_filename = f"{folder_name}_{thickness_str}in.STEP"
        output_path = os.path.join(folder_path, output_filename)

        nested_model = nesting.model_nest(placed_parts)
        _ = nesting.check_z_alignment(nested_model, thickness)
        # alignment checker will print information if the model is not aligned
        # we do not need the return bool from it through
        
        get_yield(nested_model, sheet_width, sheet_height)
        cq.exporters.export(nested_model, output_path, exportType="STEP")


def get_yield(nested_model: cq.Workplane, sheet_width: float, sheet_height: float):
    nested_bbox = nested_model.combine().val().BoundingBox()
    nested_area = nested_bbox.xlen * nested_bbox.ylen

    bottom_faces = nested_model.faces("Z").filter(lambda f: f.Center().z < 1e-5)
    part_area = sum(f.Area() for f in bottom_faces.objects)
    z_floor = nested_bbox.zmin 
    bottom_faces = nested_model.faces("<Z").filter(lambda f: abs(f.Center().z - z_floor) < 1e-3)
    part_area = sum(f.Area() for f in bottom_faces.objects)

    sheet_area = sheet_width * sheet_height
    nest_yield =  part_area / (nested_area + 0.0001)
    sheet_yield = part_area / sheet_area
    rect_yield = (sheet_area - nested_area) / sheet_area
    print(f"Nest yield: {nest_yield}\nSheet yield: {sheet_yield}\nRectangular yield: {rect_yield}")


if __name__ == "__main__":
    main()