"""
examples/xrr_thin_film.py — Example: XRR simulation of a thin SiO2 film on Si.

Demonstrates the XROSS Python API for computing an XRR curve and
evaluating fit quality using the Parratt recursion.

Usage:
    python examples/xrr_thin_film.py
"""

import numpy as np
import matplotlib.pyplot as plt
from xross.core import parratt
from xross.xrr import fit_xrr_residual

# --- Layer model: vacuum / SiO2 (20 nm) / Si substrate ---
#
# Each layer: (n, k).  For Cu-Kα (0.15418 nm):
#   vacuum:  n=1, k=0
#   SiO2:    n≈1-7.12e-6, k≈8.05e-8    (ρ≈2.2 g/cm³)
#   Si:      n≈1-7.58e-6, k≈1.73e-7    (ρ≈2.33 g/cm³)

n_arr = np.array([1.0,        1.0 - 7.12e-6, 1.0 - 7.58e-6])
k_arr = np.array([0.0,        8.05e-8,        1.73e-7])
d_nm  = np.array([0.0,        20.0,           0.0])       # thickness
s_nm  = np.array([0.0,        0.3,            0.2])       # roughness
lam   = 0.15418  # Cu-Kα in nm

# --- Simulate XRR curve ---
theta = np.linspace(0.1, 4.0, 1000)
R = parratt(theta, n_arr, k_arr, d_nm, s_nm, lam)

print(f"Layers: vacuum / SiO2 (20 nm, σ=0.3 nm) / Si (σ=0.2 nm)")
print(f"Wavelength: {lam} nm (Cu-Kα)")
print(f"Theta range: {theta[0]:.1f}° – {theta[-1]:.1f}° ({len(theta)} points)")
print(f"R at 0.5°: {R[np.argmin(abs(theta-0.5))]:.4e}")

# --- Verify self-consistency: fit residual against itself → χ²≈0 ---
chi2, y_calc = fit_xrr_residual(theta, R, n_arr, k_arr, d_nm, s_nm, lam)
print(f"Self-fit χ²: {chi2:.2e} (should be ~0)")

# --- Demonstrate effect of thickness change ---
d_nm_shifted = np.array([0.0, 25.0, 0.0])  # 25 nm instead of 20
R_shifted = parratt(theta, n_arr, k_arr, d_nm_shifted, s_nm, lam)

# --- Plot ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8))

ax1.semilogy(theta, R, "b-", lw=1.2, label="SiO₂ 20 nm")
ax1.semilogy(theta, R_shifted, "r--", lw=1.2, label="SiO₂ 25 nm")
ax1.set_xlabel("Theta (deg)")
ax1.set_ylabel("Reflectivity")
ax1.set_title("XRR: SiO₂ thin film on Si substrate")
ax1.legend()
ax1.grid(True, which="both", alpha=0.3)

# Fresnel-normalised (R × θ⁴)
ax2.plot(theta, R * theta**4, "b-", lw=1.2, label="20 nm × θ⁴")
ax2.plot(theta, R_shifted * theta**4, "r--", lw=1.2, label="25 nm × θ⁴")
ax2.set_xlabel("Theta (deg)")
ax2.set_ylabel("R × θ⁴")
ax2.set_title("Fresnel-normalised (Kiessig fringes)")
ax2.legend()
ax2.grid(True, alpha=0.3)

fig.tight_layout()
plt.savefig("xrr_thin_film.png", dpi=150)
plt.show()
