"""
examples/euv_mosi_reflectivity.py — Example: Mo/Si multilayer reflectivity.

Demonstrates the XROSS Python API for simulating a 40-pair Mo/Si
EUV multilayer mirror at 13.5 nm.

Usage:
    python examples/euv_mosi_reflectivity.py
"""

import numpy as np
import matplotlib.pyplot as plt
from xross import Layer, build_stack, reflectivity_matrix

# --- Define materials ---
Mo = Layer("Mo", n=0.9212, k=0.00643, thickness_nm=2.8, roughness_nm=0.3)
Si = Layer("Si", n=0.9999, k=0.00183, thickness_nm=4.1, roughness_nm=0.3)
Vac = (1.0, 0.0, 0.0, 0.0)

# --- Build 40-pair multilayer ---
n_pairs = 40
stack = [Vac] + build_stack([Mo, Si], repeat=n_pairs) + [Si.as_tuple()]
print(f"Stack: {len(stack)} layers ({n_pairs} Mo/Si pairs)")

# --- Wavelength scan at 6° incidence ---
wavelengths = np.linspace(12.0, 15.0, 500)
R_wl = [reflectivity_matrix(stack, lam, 6.0)[0] * 100 for lam in wavelengths]

# --- AOI scan at 13.5 nm ---
angles = np.linspace(0.1, 30.0, 300)
R_aoi = [reflectivity_matrix(stack, 13.5, a)[0] * 100 for a in angles]

# --- Plot ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

ax1.plot(wavelengths, R_wl, "b-", lw=1.5)
ax1.set_xlabel("Wavelength (nm)")
ax1.set_ylabel("Reflectivity (%)")
ax1.set_title(f"Mo/Si {n_pairs}-pair — Wavelength scan (AOI=6°)")
ax1.grid(True, alpha=0.3)
ax1.axvline(13.5, color="r", ls="--", alpha=0.5, label="13.5 nm")
ax1.legend()

ax2.plot(angles, R_aoi, "g-", lw=1.5)
ax2.set_xlabel("Angle of incidence (deg)")
ax2.set_ylabel("Reflectivity (%)")
ax2.set_title(f"Mo/Si {n_pairs}-pair — AOI scan (λ=13.5 nm)")
ax2.grid(True, alpha=0.3)

fig.tight_layout()
plt.savefig("euv_mosi_reflectivity.png", dpi=150)
plt.show()

print(f"\nPeak reflectivity at 13.5 nm, 6°: {reflectivity_matrix(stack, 13.5, 6.0)[0]*100:.1f}%")
