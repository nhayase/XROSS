# XROSS
XROSS is the Python-based simulator for X-ray optics. It is completely free and open source software. 
You can simulate EUV reflectivity, X-ray reflectivity (XRR) analysis, and nanoscale deposition optimization for roughness control.

Please cite as follow when you use for your publications & presentations.  

    Naoki Hayase, "XROSS - X-Ray Optics Simulation Software," arXiv (2024)

## Installation

(1) Download from here & you can get "xross.exe" in the top folder.

(2) Click "xross.exe".

## Usage

(1) Modelling a structure by "Layer" (a single layer) & "Subroutine" (a multilayer) on the main window.
→ When you need to delete "Layer" or "Subroutine", click the toggles (& it changes the color) on the left side.
→ You can save your models as csv files and load them.
→ When you save files, it is automatically logged on the Log Window & written in text files on the top folder next to "xross.exe".

(2) EUV reflectivity → Open EUV Optics Window from the main window. You need to setup optical parameters & "Calculation".

(3) XRR analysis → Open XRR Analysis Window from the main window. You need to load .xrfml file & "Run".

(3) XRR analysis → Open Deposition Window from the main window. You need to setup optical parameters & Run.

## Reference

[1]	D. L. Windt, IMD—Software for modeling the optical properties of multilayer films. Computers in physics, 12(4), 360-370 (1998). 

[2]	L. G. Parratt, “Surface studies of solids by total reflection of X-rays,” Physical Review, 95(2), 359. (1954).

[3] O. V. Penkov, M. Li, S. Mikki, A. Devizenko, I. Kopylets, “X-Ray Calc 3: improved software for simulation and inverse problem solving for X-ray reflectivity,” Journal of Applied Crystallography, 57(2), 555-566 (2024).
[4] T. Akiba, S. Sano, T. Yanase, T. Ohta, M. Koyama, “Optuna: A next-generation hyperparameter optimization framework,” Proceedings of the 25th ACM SIGKDD international conference on knowledge discovery & data mining, 2623-2631 (2019).

[5] F. Lundh, "An introduction to tkinter," www.pythonware.com/library/tkinter/introduction/index.htm (1999).

[6] N. Hayase, T. Harada, “Beyond EUV binary and phase shift masks simulation”, Proc. SPIE, Vol. 13177, (2024).

[7] N. Hayase, T. Harada, “EUV scattering analysis of surface growth in multilayer via the KPZ equation,” (to be published).

