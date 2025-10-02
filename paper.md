XROSS – X-Ray Optics Simulation Software
Naoki Hayase1
1 Center for EUV Lithography, LASTI, University of Hyogo, Ako-gun, Kouto, Hyogo, 651-2492, Japan.

Summary
We present XROSS, a Python‑based X‑ray optics simulator designed for evaluating of nanoscale thin films. XROSS provides a user‑friendly interface that integrates (i) calculation of optical properties and X‑ray reflectivity (XRR), (ii) particle swarm optimization (PSO)‑assisted XRR analysis, and (iii) deposition process optimization via surface growth models. Our key contribution is the high‑precision estimation of thin film density that governs the complex refractive index in the X‑ray regime. In this study, we use black‑box optimization with the Optuna library, achieving half runtime XRR fitting than conventional PSO. We also apply Optuna to deposition process optimization for simulating thin film roughness and density based on statistical physics; the Kardar-Parisi-Zhang (KPZ) equation and the solid-on-solid (SOS) model. These simulations improve the prediction of thin film density by fitting the density scan from surface growth and complex refractive index from reflectivity. 

Statement of need
X-ray analysis software requires user-friendly interface, short-time analysis, and precise calculations for nanoscale structures. We have developed XROSS as a successor to the X-ray reflectivity simulator IMD (D. L. Windt, 1998), and users can freely use without programming knowledge. XROSS simulates optical properties of multilayer films based on the Parratt model (L. G. Parratt, 1954), and it can also evaluate new parameters of X-ray multilayer, such as an effective reflection plane (E. Van Setten et al., 2020). 
X-ray reflectivity (XRR) analysis needs to minimize non-convex and non-linear objective functions, but gradient calculation is difficult because analytical expressions for hierarchy structures with reflectivity. X-Ray Calc 3 (O. V. Penkov et al., 2024) have applied the particle swarm optimization (PSO) for XRR analysis, and search for local optima. However, the PSO depends on number of trials and takes a long time. In this study, we introduce Optuna (T. Akiba et al., 2019) which use Bayesian and gradient-free black-box optimization for short-time converge. Optuna requires lower computer resources for calculating parameter ranges and scales (thickness, density, and roughness).
We propose an optimal deposition simulation of surface roughness and scattered light intensity, based on the Kardar-Parisi-Zhang (KPZ) equation and the solid-on-solid (SOS) model. Using experimental data with Optuna, the coefficients of the KPZ equation terms are updated and improve simulation accuracy of roughness. It aims to predict deposition feasibility close to fitting models to experiment by statistical trends.

Usage
XROSS user interface is built by the Python library tkinter (F. Lundh, 1999), and structure models are built by “Layer” and “Subroutine” enabling to set several parameters in the XROSS window: refractive index, extinction coefficient, thickness, density, and roughness. Prepared models can save them as csv files. The log window from the main window displays a message when commands are executed and save file history in the text file. The EUV optics window calling from the main window, and we can simulate a reflectivity at an arbitrary wavelength. XROSS has proven a calculation for beyond EUV multilayers at 6.7 nm wavelength (N. Hayase et al., 2024).
The XRR analysis window and XROSS requires an evaluated model and XRR experimental data (.xrdml file). When “Run” is executed, a fitting curve is draw in a graph and the degree of agreement between the fitting curves is determined by the chi-square value. The coefficients of the fitting curve in simulations are output as csv files. The number of trials can be set and repeated for the minimization until the chi-square becomes saturated.
In the deposition window, we assume the solid-on solid model which particles are flight and attach at random to lattice points in a plane and output analytical values by the KPZ equation. We show the surface growth model in 2+1 dimensions by material parameters: roughness, surface energy, and crystallinity as deposition process (N. Hayase et al., 2025).

Acknowledgements
This work was supported by the research grant from Hyogo Earthquake Memorial 21st Century Research Institute, Japan.

References
1.	D. L. Windt, IMD—Software for modeling the optical properties of multilayer films. Computers in physics, 12(4), 360-370 (1998). 
2.	L. G. Parratt, “Surface studies of solids by total reflection of X-rays,” Physical Review, 95(2), 359. (1954).
3.	E. Van Setten, K. Rook, H. Mesilhy, G. Bottiglieri, F. Timmermans, M. Lee, A. Erdmann, T. Brunner, “Multilayer optimization for high-NA EUV mask3D suppression,” Proc. SPIE, Vol. 11517, pp. 78-88 (2020).
4.	O. V. Penkov, M. Li, S. Mikki, A. Devizenko, I. Kopylets, “X-Ray Calc 3: improved software for simulation and inverse problem solving for X-ray reflectivity,” Journal of Applied Crystallography, 57(2), 555-566 (2024).
5.	T. Akiba, S. Sano, T. Yanase, T. Ohta, M. Koyama, “Optuna: A next-generation hyperparameter optimization framework,” Proceedings of the 25th ACM SIGKDD international conference on knowledge discovery & data mining, 2623-2631 (2019).
6.	F. Lundh, "An introduction to tkinter,"
www.pythonware.com/library/tkinter/introduction/index.htm (1999).
7.	N. Hayase, T. Harada, “Beyond EUV binary and phase shift masks simulation”, Proc. SPIE, Vol. 13177, (2024).
8.	N. Hayase, T. Harada, “EUV scattering analysis of surface growth in multilayer via the KPZ equation,” (to be published).


