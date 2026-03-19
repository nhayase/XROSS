---
title: 'XROSS: X-Ray Optics Simulation Software'
tags:
  - Python
  - X-ray optics
  - EUV lithography
  - multilayer reflectivity
  - XRR analysis
  - optimization
authors:
  - name: Naoki Hayase
    orcid: 0009-0005-4310-7961
    affiliation: 1
affiliations:
  - name: University of Hyogo, Japan
    index: 1
date: 1 September 2025
bibliography: paper.bib
---

# Summary

We present XROSS, a Python‑based X‑ray optics simulator designed for evaluation of nanoscale thin films. XROSS provides a user‑friendly platform for analyzing reflectivity measurements such as X‑ray reflectivity (XRR) and extreme ultraviolet (EUV) reflectivity. In semiconductor engineering, the X-ray reflectivity simulator IMD is well-known to estimate reflectivity, but multiple wavelengths and incident angles must be calculated individually and manually. Thus, we have automated the calculation process while maintaining accuracy for comparison with each result. The algorithm is based on particle swarm optimization (PSO), and we use Optuna, the Python library to shorten XRR fitting runtime. Furthermore, we propose the optimization model using arbitrary parameters approach to feedback optimal condition from analyzed results. We confirmed the optimization modelling to construct a surrogate model from a small amount of experimental data to identify the optimal conditions. This tool is connected to NewSUBARU synchrotron radiation facility. 

# Statement of need

X-ray analysis software requires user-friendly platform, short-time analysis, and precise calculations for nanoscale structures. NewSUBARU synchrotron radiation facility can measure soft X-ray reflectivity from 2 nm to 14 nm, and requires IMD [@windt1998], the X-ray reflectivity simulator for analyzing measured data. We have developed XROSS as a successor to IMD, and users can freely simulates optical reflectivity of monolayers and multilayers without programming knowledge. Reflectivity calculation in XROSS is based on the Parratt model [@parratt1954], and it enables automatic estimation of refractive index and extinction coefficient at multiple wavelengths and incident angles from measured reflectivity. 

X-ray reflectivity (XRR) analysis needs to minimize non-convex and non-linear objective functions. X-Ray Calc 3 [@penkov2024] adopted particle swarm optimization (PSO) to address this problem, demonstrating that derivative-free global search is effective for XRR curve fitting. Nevertheless, PSO convergence is slow when the number of fitting parameters increases, since the swarm must explore a high-dimensional space without prior knowledge. XROSS accelerates convergence by combining Optuna's Tree-structured Parzen Estimator (TPE) [@akiba2019] with PSO. TPE constructs a Bayesian surrogate of the objective function and proposes promising trial points, providing the subsequent PSO stage with a warm-start solution that is already near the global basin. In benchmark tests on single-layer and multilayer models, this two-stage strategy reduced the number of function evaluations required to reach a given chi-squared threshold by approximately a factor of three compared with PSO alone.

Deposition process is optimized by parameters in experiments. Efficient optimization is required, but open source for multi-objective optimization are not much and limits in terms of ease of use. XROSS provides multi-objective optimization designed by Optuna with experimental data. We can apply the model for deposition simulation. Using experimental data with Optuna, the parameters are updated and improve estimation accuracy. It aims to predict deposition feasibility close to fitting models to experiment by statistical trends. 

# State of the field

Several established software packages exist for X-ray and neutron reflectivity analysis. GenX [@bjorck2007] uses differential evolution for fitting reflectivity data and provides a plugin architecture for different scattering models. refnx [@nelson2019] provides a flexible Bayesian inference framework built on the Markov chain Monte Carlo (MCMC) sampler emcee, enabling uncertainty quantification alongside parameter estimation. For EUV lithography at 13.5 nm, IMD is a widely used but proprietary tool for optical design of multilayer coatings.

For multi-objective optimization, commercial platforms provide GUI-driven workflows using deep learning and genetic algorithms, but they are not open-source and cannot be extended or audited by the research community. General-purpose frameworks such as pymoo and DEAP implement NSGA-II and other evolutionary algorithms but require users to define their own problem interfaces.

XROSS distinguishes itself by integrating reflectivity physics, XRR curve fitting, and surrogate-model-based multi-objective optimization into a cohesive open-source package with a domain-specific GUI designed specifically for the thin-film and EUV optics workflow.

# Software design

XROSS has a modular architecture with a strict separation between computational kernels and the graphical interface. All physics and optimization code relies solely on NumPy and runs without any GUI toolkit, allowing it to be used in batch mode on computing clusters.

The package is organised into five modules:

- **`xross.core`** implements the transfer-matrix method for multilayer reflectivity calculation and the Parratt recursion for specular XRR. It also provides a robust parser for optical-constants files (nk format) with automatic wavelength-unit conversion from Angstroms to nanometres and LRU caching for repeated reads. All functions accept and return NumPy arrays, making them composable with the wider scientific Python ecosystem.

- **`xross.xrr`** provides the XRR analysis pipeline. This includes a loader for PANalytical XRDML files, a peak-preserving downsampling algorithm that retains Kiessig fringes while reducing the number of evaluation points for faster fitting, and a weighted log-residual objective function with automatic intensity scaling. The fitting engine uses a particle-swarm optimiser with Nevot-Croce roughness throughout for physical consistency, augmented by a shake-restart mechanism that escapes local minima by periodically randomising the swarm. Measured reflectivity data from NewSUBARU synchrotron radiation facility can be analyzed to estimate refractive index and extinction coefficient.

- **`xross.optimize`** implements the NSGA-II multi-objective genetic algorithm with simulated binary crossover (SBX) and polynomial mutation based on Optuna. The module accepts an arbitrary evaluation function, which in the GUI is an IDW surrogate model trained from user-supplied CSV data. This design keeps the optimization engine generic and testable independent of any specific machine-learning library.

- **`xross.fileio`** handles serialisation of layer models and results to CSV format with timestamped logging.

- **`xross.gui`** provides the Tkinter-based graphical interface, organised into sub-modules for the main window (layer and subroutine management), EUV optics (all scan types plus multi-CSV overlay), XRR analysis (data loading and live-updating fit plots), and the optimization window (variable assignment, training, feature importance, NSGA-II, and single/batch prediction).

# Research impact statement

XROSS has been developed to support ongoing multilayer mirror research at NewSUBARU synchrotron radiation facility. It is currently used for X-ray reflectivity simulation and XRR analysis of multilayer structures for next-generation lithography applications [@hayase2024]. The optimization module has been applied to deposition condition screening. The software is designed to be immediately useful to the broader thin-film and EUV optics research community, and the open-source release is intended to enable reproducible research and developing an efficient experimental design [@hayase2026].

# AI usage disclosure

Author made entirely the core design and coding, including the transfer-matrix with the Parratt model, the Optuna-based optimization, the layer/subroutine data model. Portions of the code correction removing syntax errors are assisted by Claude (Anthropic.com), and iThenticate (Turnitin.com) for plagiarism detection.

# Acknowledgements

This work was supported by Hyogo Earthquake Memorial 21st Century Research Institute, and Hyogo Foundation for Science and Technology.


