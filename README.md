**About**

This program is designed for use with the workflow of multiple SolidWorks users creating sheet metal parts which will be exported as step files and imported into Fusion360 for CAM programming. It is intended to be a script that is run from the terminal or an executable.

At the moment program uses CAM parameters (from machineParameters.json) for CNC Plasma cutter. The sheets are sized according to what the machine can handle (in sheets.csv).

Future changes would include the ability to nest to non-rectangular remnants and an improved nesting algorithm. The imrpovements to the nesting algorithm begin with trueshape nesting then Hueristic approaches such as a genetic algorithm for part order. Another addition would be common cut however this is not always desireable with CNC plasma due to their taper angle. 

Since one of the primary dependancies, CadQuery, uses millimeters and degrees the majority of the inputs are such. A future improvement would be to switch all inputs to inches.

I may make it to where the user is given a pop-up for the parts, the sheet, and a BOM-type form to take in the input. If you have thoughts on a good, and lightweight interface please let me know! 

**AI Usage Disclosure**

The first itteration was primarily handwritten. Later into the project, I found it convenient to provide AI with the core logic I was looking for (what and how to do the nfp) and have it generate code with the sytax.

**How it works**

The program imports STEP files and identifies each part's thickness as the smallest bounding box dimension, reorienting all models so the thickness aligns with the z-axis. Parts are then grouped by thickness. For each group, parts are sorted largest-to-smallest by bounding box area and nested onto the sheet using a bottom-left trueshape nesting algorithm -- each part is tried at 8 rotation angles (0–315-deg in 45-deg steps) and placed at the first candidate position that fits within the sheet boundary without overlapping already-placed parts.

**To have this available on your desktop**
1. Download the python source files and the data files
2. Create and install the dependancies to a virtual enviroment
3. Run from terminal or IDE
4. (OPTIONAL) If everything is working then bundle/transpile
