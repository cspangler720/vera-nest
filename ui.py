# Copyright (c) 2026 Carter Spangler
# Licensed under the MIT License. 
# See LICENSE file in the project root for full license information.

# this module is entirely AI generated

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, Optional

def read_csv(file_path: str) -> List[List[str]]:
    """Read a CSV file and return its contents as a 2D list."""
    import os
    import csv
    if not os.path.exists(file_path):
        print(f"CSV file not found: {file_path}")
        return []
    with open(file_path, 'r') as file:
        return list(csv.reader(file))

def on_row_select(
    event,
    tree: ttk.Treeview,
    sheets: List[List[str]],
    result_container: dict
) -> None:
    """Handle row selection and store sheet_width and sheet_height in result_container."""
    selected_item = tree.selection()[0]
    row_index = int(selected_item) - 1  # Adjust for 1-based indexing in Treeview
    row = sheets[row_index]

    if len(row) < 2:
        print("Row does not contain enough values for width and height!")
        return

    try:
        sheet_width = float(row[0])
        sheet_height = float(row[1])
        result_container["sheet_width"] = sheet_width
        result_container["sheet_height"] = sheet_height
        print(f"Selected sheet dimensions: ({sheet_width}, {sheet_height})")
        tree.master.destroy()  # Close the pop-up window
    except ValueError:
        print("Row contains non-numeric values for width or height!")

def create_sheet_selection_gui(sheets: List[List[str]]) -> Tuple[Optional[float], Optional[float]]:
    """
    Create a GUI to select a sheet and return (sheet_width, sheet_height).
    Returns (None, None) if no valid selection is made.
    """
    result = {"sheet_width": None, "sheet_height": None}

    root = tk.Tk()
    root.title("Select Sheet Dimensions")

    # Create a treeview (table) widget
    tree = ttk.Treeview(root)
    tree["columns"] = [f"col_{i}" for i in range(len(sheets[0]))]
    tree["show"] = "headings"

    # Set column headings
    for i, col in enumerate(sheets[0]):
        tree.heading(f"col_{i}", text=col)
        tree.column(f"col_{i}", width=100)

    # Add rows to the treeview (skip header if present)
    for i, row in enumerate(sheets[1:], start=1):
        tree.insert("", "end", values=row, iid=i)

    # Bind double-click to select a row
    tree.bind("<Double-1>", lambda event: on_row_select(event, tree, sheets[1:], result))

    # Pack the treeview
    tree.pack(expand=True, fill="both")

    root.mainloop()

    return result["sheet_width"], result["sheet_height"]