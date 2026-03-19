"""
xross.core — Physics engine for multilayer X-ray / EUV reflectivity.

This module contains all computational routines, fully independent of GUI.
Every function is pure (no side effects) and suitable for scripting, testing,
and batch calculations.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Sequence, Tuple

import numpy as np

__all__ = [
    "reflectivity_matrix",
    "parratt",
    "parse_nk_file",
    "interp_nk",
    "Layer",
    "build_stack",
]


# -----------------------------------------------------------------------
#  Data structures
# -----------------------------------------------------------------------

class Layer:
    """Immutable description of a single thin-film layer.

    Parameters
    ----------
    name : str
        Material identifier (e.g. ``"Mo"``, ``"Si"``).
    n : float
        Real part of the refractive index.
    k : float
        Imaginary part (extinction coefficient).
    thickness_nm : float
        Layer thickness in nanometres.
    density_gcm3 : float
        Bulk density in g cm⁻³  (used when *n*, *k* are not provided).
    roughness_nm : float
        RMS interfacial roughness in nanometres (Névot–Croce model).
    """

    __slots__ = ("name", "n", "k", "thickness_nm", "density_gcm3", "roughness_nm")

    def __init__(
        self,
        name: str = "",
        n: float = 1.0,
        k: float = 0.0,
        thickness_nm: float = 0.0,
        density_gcm3: float = 0.0,
        roughness_nm: float = 0.0,
    ):
        self.name = name
        self.n = float(n)
        self.k = float(k)
        self.thickness_nm = float(thickness_nm)
        self.density_gcm3 = float(density_gcm3)
        self.roughness_nm = float(roughness_nm)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        """Return ``(n, k, thickness_nm, roughness_nm)``."""
        return (self.n, self.k, self.thickness_nm, self.roughness_nm)

    def __repr__(self) -> str:
        return (
            f"Layer({self.name!r}, n={self.n}, k={self.k}, "
            f"d={self.thickness_nm} nm, ρ={self.density_gcm3} g/cm³, "
            f"σ={self.roughness_nm} nm)"
        )


# -----------------------------------------------------------------------
#  Stack builder
# -----------------------------------------------------------------------

def build_stack(
    layers: Sequence[Layer],
    repeat: int = 1,
    *,
    cap: Layer | None = None,
) -> list[tuple[float, float, float, float]]:
    """Build a full layer stack as a list of ``(n, k, d, σ)`` tuples.

    Parameters
    ----------
    layers : sequence of :class:`Layer`
        The unit cell (e.g. one Mo/Si bilayer).
    repeat : int
        Number of repetitions of the unit cell.
    cap : Layer or None
        Optional capping layer appended on top.

    Returns
    -------
    list of (n, k, d_nm, σ_nm)
    """
    stack = []
    for _ in range(max(1, int(repeat))):
        for lay in layers:
            stack.append(lay.as_tuple())
    if cap is not None:
        stack.append(cap.as_tuple())
    return stack


# -----------------------------------------------------------------------
#  Transfer-matrix reflectivity  (EUV Optics)
# -----------------------------------------------------------------------

def reflectivity_matrix(
    layer_stack: Sequence[tuple[float, float, float, float]],
    wavelength_nm: float,
    angle_deg: float,
) -> Tuple[float, float]:
    """Compute reflectivity and phase using the transfer-matrix method.

    Parameters
    ----------
    layer_stack : sequence of (n, k, d_nm, σ_nm)
        From top (vacuum-side) to bottom (substrate).
    wavelength_nm : float
        Wavelength in nanometres.
    angle_deg : float
        Angle of incidence in degrees.

    Returns
    -------
    reflectivity : float
        Power reflectance (0–1).
    phase : float
        Reflected-wave phase in radians.
    """
    theta = np.radians(angle_deg)
    lam = float(wavelength_nm)

    def kz(n, k):
        return (2 * np.pi / lam) * (n - 1j * k) * np.cos(theta)

    def fresnel(n1, k1, s1, n2, k2, s2):
        kz1, kz2 = kz(n1, k1), kz(n2, k2)
        r12 = (kz1 - kz2) / (kz1 + kz2)
        return r12 * np.exp(-2 * (kz1 * kz2 * (s1 + s2)) ** 2)

    M = np.eye(2, dtype=complex)
    for j in range(len(layer_stack) - 1):
        n1, k1, d1, s1 = layer_stack[j]
        n2, k2, _, s2 = layer_stack[j + 1]

        r12 = fresnel(n1, k1, s1, n2, k2, s2)
        kz1 = kz(n1, k1)

        M_prop = np.array(
            [[np.exp(-1j * kz1 * d1), 0], [0, np.exp(+1j * kz1 * d1)]]
        )
        M_bnd = np.array(
            [[1 / (1 + r12), r12 / (1 + r12)], [r12 / (1 + r12), 1 / (1 + r12)]]
        )
        M = M_bnd @ M_prop @ M

    r_tot = -M[1, 0] / M[1, 1]
    return float(abs(r_tot) ** 2), float(np.angle(r_tot))


# -----------------------------------------------------------------------
#  Parratt recursion  (XRR Analysis)
# -----------------------------------------------------------------------

def parratt(
    theta_deg: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d_nm: np.ndarray,
    sigma_nm: np.ndarray,
    wavelength_nm: float,
) -> np.ndarray:
    """Parratt recursion for specular X-ray reflectivity.

    Parameters
    ----------
    theta_deg : 1-D array
        Incidence angles in degrees.
    n_arr, k_arr : 1-D arrays  (length N_layers)
        Complex refractive index ``n - i·k`` per layer, top to bottom.
    d_nm : 1-D array  (length N_layers)
        Thickness per layer in nm  (first & last may be 0 for vacuum / substrate).
    sigma_nm : 1-D array  (length N_layers)
        Interfacial roughness per layer in nm.
    wavelength_nm : float
        X-ray wavelength in nm.

    Returns
    -------
    reflectivity : 1-D array
        |r|² at each angle.
    """
    theta = np.asarray(theta_deg, dtype=float)
    cos_t = np.cos(np.radians(theta))
    k0 = 2.0 * np.pi / float(wavelength_nm)

    m = (np.asarray(n_arr, float) - 1j * np.asarray(k_arr, float)).astype(
        np.complex128
    )
    d = np.asarray(d_nm, float)
    s = np.asarray(sigma_nm, float)

    kz = k0 * np.sqrt(m[:, None] ** 2 - cos_t[None, :] ** 2)

    r = np.zeros_like(cos_t, dtype=np.complex128)
    for j in range(len(m) - 2, -1, -1):
        rj = (kz[j] - kz[j + 1]) / (kz[j] + kz[j + 1])
        sig = 0.5 * (s[j] + s[j + 1])
        if sig > 0.0:
            rj *= np.exp(-2.0 * kz[j] * kz[j + 1] * sig ** 2)
        phase = np.exp(2j * kz[j + 1] * d[j + 1])
        r = (rj + r * phase) / (1.0 + rj * r * phase)

    return (np.abs(r) ** 2).astype(float)


# -----------------------------------------------------------------------
#  nk file parser
# -----------------------------------------------------------------------

@lru_cache(maxsize=64)
def parse_nk_file(path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse an optical-constants file (λ[Å]  n  k).

    Parameters
    ----------
    path : str
        File path. Columns: wavelength(Å), n, k.  Comments start with
        ``#``, ``//``, or ``;``.

    Returns
    -------
    wavelength_nm : 1-D array
        Wavelength in *nanometres* (sorted, unique).
    n : 1-D array
    k : 1-D array
    """
    lam_A: list[float] = []
    n_list: list[float] = []
    k_list: list[float] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            s = s.split("#")[0].split("//")[0].split(";")[0].strip()
            if not s:
                continue
            parts = re.split(r"[,\s]+", s)
            if len(parts) < 3:
                continue
            try:
                la, n_val, k_val = float(parts[0]), float(parts[1]), float(parts[2])
            except ValueError:
                continue
            lam_A.append(la)
            n_list.append(n_val)
            k_list.append(k_val)

    if not lam_A:
        raise ValueError("No numeric rows (λ[Å] n k) found in file.")

    lam_nm = np.asarray(lam_A, float) / 10.0  # Å → nm
    n_arr = np.asarray(n_list, float)
    k_arr = np.asarray(k_list, float)
    idx = np.argsort(lam_nm)
    lam_nm, n_arr, k_arr = lam_nm[idx], n_arr[idx], k_arr[idx]
    _, uniq = np.unique(lam_nm, return_index=True)
    return lam_nm[uniq], n_arr[uniq], k_arr[uniq]


def interp_nk(
    target_nm: np.ndarray,
    lam_nm: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate *n* and *k* onto *target_nm*.

    Parameters
    ----------
    target_nm : 1-D array
        Wavelengths at which to evaluate.
    lam_nm, n_arr, k_arr : 1-D arrays
        Tabulated optical constants (as returned by :func:`parse_nk_file`).

    Returns
    -------
    n_interp, k_interp : 1-D arrays
    """
    return (
        np.interp(target_nm, lam_nm, n_arr),
        np.interp(target_nm, lam_nm, k_arr),
    )
