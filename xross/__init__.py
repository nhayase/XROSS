"""
XROSS – X-Ray Optics Simulation Software
=========================================

A Python toolkit for multilayer EUV/X-ray reflectivity simulation,
XRR analysis, and multi-objective process optimisation.

Modules
-------
core
    Physics engine: reflectivity (transfer-matrix & Parratt), nk parser.
xrr
    XRR fitting pipeline and .xrdml loader.
optimize
    NSGA-II multi-objective optimisation.
fileio
    CSV I/O for layer models and results.
gui
    Tkinter-based graphical user interface (optional).
"""

__version__ = "2.0.1"
__author__ = "Naoki Hayase"

from xross.core import (
    Layer,
    build_stack,
    interp_nk,
    parse_nk_file,
    parratt,
    reflectivity_matrix,
)
from xross.xrr import load_xrdml
from xross.optimize import nsga2, OptimizationProblem

__all__ = [
    "Layer",
    "build_stack",
    "interp_nk",
    "parse_nk_file",
    "parratt",
    "reflectivity_matrix",
    "load_xrdml",
    "nsga2",
    "OptimizationProblem",
]
