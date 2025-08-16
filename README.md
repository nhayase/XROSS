# XROSS
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

→ When you modify an arrangement of "Layer" & "Subroutine", click the toggles (& it changes blue color) on the left side & click "Up" or "Down".

→ When you need to delete "Layer" or "Subroutine", click the toggles on the left side & click "Delete Layer" or "Del Subroutine".

→ After modelling, you can save your models as csv files and load them.

→ When you save files, it is logged on the Log Window & written in text files on the top folder next to "xross.exe".

### 2. EUV reflectivity 
→ Open EUV Optics Window from the main window. You need to setup optical parameters & "Calculation".

### 3. XRR analysis 
→ Open XRR Analysis Window from the main window. You need to load .xrfml file & "Run".

### 4. Deposition Optimization 
→ Open Deposition Window from the main window. You need to setup optical parameters & Run.


