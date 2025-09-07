# XROSS (Sep. 2025 Demo the 1st ver.)
XROSS is the Python-based simulator for X-ray optics. It is completely free and open source software. 
You can simulate optical reflectivity, X-ray reflectivity (XRR) analysis, and nanoscale deposition optimization for roughness control.

Please cite it as follows when using it in your publications and presentations:  

    Naoki Hayase, "XROSS - X-Ray Optics Simulation Software," arXiv (2025).

## Installation

(1) Download "xross" folder (containing folders of "art", "doc", "geo", "icon", "save", "xrr" and log.txt, xross.py, xross.exe).

(2) Click "xross.exe".

## Usage

### 1. Modelling 
→ Modelling a structure by "Layer" (a single layer) & "Subroutine" (a multilayer) on the main window.

→ Right-click on "Subroutine", you can setup a number of pairs (& its name) as a multilayer.

→ Click the toggles (it changes blue color) on the left side of "Layer", you can modify an arrangement of them & click "Up" or "Down".

→ Click the toggles & "Delete Layer" or "Del Subroutine", you can delete them.

→ You can save your model as csv files and load them.

→ When you save files, it is logged on the Log Window & written in text files on the top folder next to "xross.exe".

### 2. EUV reflectivity 
→ Open EUV Optics Window. 

→ Modelling or Load your model on the main menu. 

→ Check-in your tests after fulfill the value & click "Calculation".

### 3. XRR analysis 
→ Open XRR Analysis Window. 

→ Modelling or Load your model on the main menu.

→ Load .xrfml file & click "Run".

### 4. Deposition Optimization 
→ Open Deposition Window. 

→ You need to setup optical parameters & Run.


