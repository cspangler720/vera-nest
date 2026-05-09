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
    machine_parameters = read_json('.\data\machineParameters.json')["parameters"]

    file_paths = filedialog.askopenfilenames(
        defaultextension=".STEP",
        filetypes=[("STEP Files", "*.STEP *.STP")]
    )

    parts_data: List[models.PartData] = loader.load_models(file_paths)
    if not parts_data:
        print("No parts loaded")
        return

    thickness_groups = nesting.group_thickness(parts_data)

    sheets = read_csv('.\data\sheets.csv')

    if sheets:
        sheet_width, sheet_height = ui.create_sheet_selection_gui(sheets)
        if sheet_width is None or sheet_height is None:
            print("No valid sheet dimensions selected!")
            return
    else:
        print("Sheets not found")

    # assuming all files are in the same folder
    folder_path = os.path.dirname(os.path.abspath(file_paths[0]))
    folder_name = os.path.basename(folder_path)

    machine_pad = machine_parameters["KERF"] + machine_parameters["TOLERANCE"] 
    for thickness, parts_in_group in thickness_groups.items():
        pad = machine_pad + thickness * cos(machine_parameters["TAPER_ANGLE"] * 0.01744)

        sorted_parts = nesting.sort(parts_in_group)
        placed_parts = nesting.trueshape_nesting(sorted_parts, sheet_width,
                                                  sheet_height, 
                                                  tol = 2.0, pad = pad)

        thickness_str = f"{thickness / 25.4:.4f}".replace(".", "p")
        output_filename = f"{folder_name}_{thickness_str}in.STEP"
        output_path = os.path.join(folder_path, output_filename)

        nested_model = nesting.model_nest(placed_parts)
        _ = nesting.check_z_alignment(nested_model, thickness)
        # alignment checker will give information if the model is not aligned

        cq.exporters.export(nested_model, output_path, exportType="STEP")

if __name__ == "__main__":
    main()
