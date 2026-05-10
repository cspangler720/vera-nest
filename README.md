**About**

This program is designed for use with the workflow of multiple SolidWorks users creating sheet metal parts which will be exported as step files and imported into Fusion360 for CAM programming.

At the moment program uses CAM parameters (from machineParameters.json) for CNC Plasma cutter. The sheets are sized according to what the machine can handle (in sheets.csv). 

Future changes would include the ability to nest to non-rectangular remnants and an improved nesting algorithm. Another addition would be common cut however this is not always desireable with CNC plasma due to their taper angle. Since one of the primary dependancies, CadQuery, uses millimeters and degrees the majority of the inputs are such. However, creating the option of configuring the inputs to run in mm or inches would be a potential future change. Another change would be to move the get_solids() calls to the loading module and remove redundant calls.

**AI Usage Disclosure**

The UI is AI-generated (leChat by Mistral). AI was used for syntactic corrections and research.

**How it works**

The program works by importing the files and identifying their thickness direction as the smallest bounding box direction. The models are all reoriented to align the z-axis to be the thickness direction. These the thicknesses are grouped. For each group parts are nested, largest-to-smallest, using a trueshape nesting algorithm.

**To have this available on your desktop**
1. Download the python source files and the data files
2. Create and install the dependancies to a virtual enviroment
3. Run from terminal or IDE
4. (OPTIONAL) If everything is working then bundle/transpile
