"""
xross.xrr — XRR (X-ray Reflectivity) fitting engine.

Provides data loaders for .xrdml files and a fitting pipeline that
combines Optuna (Bayesian) warm-start with particle-swarm optimisation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from xross.core import parratt

__all__ = [
    "load_xrdml",
    "peak_preserving_downsample",
    "expand_stack",
    "normalize_periodicity",
    "fit_xrr_residual",
]


# -----------------------------------------------------------------------
#  XRDML loader
# -----------------------------------------------------------------------

def load_xrdml(filepath: str) -> Optional[Dict[str, np.ndarray]]:
    """Parse a PANalytical .xrdml / .xrfml file.

    Returns
    -------
    dict with keys ``"omega"``, ``"two_theta"``, ``"y"``
    or ``None`` if parsing fails.
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        txt = f.read()

    m_counts = re.search(r"<counts[^>]*>(.*?)</counts>", txt, re.I | re.S)
    m_intens = (
        None
        if m_counts
        else re.search(r"<intensities[^>]*>(.*?)</intensities>", txt, re.I | re.S)
    )
    series = m_counts or m_intens
    if not series:
        return None

    y_raw = np.fromstring(
        re.sub(r"[^\d\.\+\-Ee]", " ", series.group(1)), sep=" "
    )
    npts = y_raw.size

    # Counting-time normalisation
    m_cct = re.search(
        r"<commonCountingTime[^>]*>(.*?)</commonCountingTime>", txt, re.I | re.S
    )
    m_ct = re.search(
        r"<countingTime[^>]*>(.*?)</countingTime>", txt, re.I | re.S
    )
    if m_cct:
        y = y_raw / float(m_cct.group(1))
    elif m_ct:
        cts = np.fromstring(
            re.sub(r"[^\d\.\+\-Ee]", " ", m_ct.group(1)), sep=" "
        )
        y = y_raw / cts if cts.size == npts else y_raw
    else:
        y = y_raw
    y = np.clip(y, 1e-12, None)

    # Beam-attenuation factors
    m_baf = re.search(
        r"<beamAttenuationFactors[^>]*>(.*?)</beamAttenuationFactors>",
        txt, re.I | re.S,
    )
    if m_baf:
        fac = np.fromstring(
            re.sub(r"[^\d\.\+\-Ee]", " ", m_baf.group(1)), sep=" "
        )
        if fac.size == npts:
            y = y * fac
        elif fac.size == 1:
            y = y * fac[0]

    # --- Axis positions ---------------------------------------------------
    def _get_positions(axis_name: str) -> Optional[np.ndarray]:
        pattern = (
            rf'<positions[^>]*axis\s*=\s*["\']{re.escape(axis_name)}'
            rf'["\'][^>]*>(.*?)</positions>'
        )
        m = re.search(pattern, txt, re.I | re.S)
        if not m:
            return None
        blk = m.group(1)
        m_list = re.search(
            r"<listPositions[^>]*>(.*?)</listPositions>", blk, re.I | re.S
        )
        if m_list:
            arr = np.fromstring(
                re.sub(r"[^\d\.\+\-Ee]", " ", m_list.group(1)), sep=" "
            )
            if arr.size == npts:
                return arr
            if arr.size > 1:
                xs = np.linspace(0, arr.size - 1, npts)
                return np.interp(xs, np.arange(arr.size), arr)
        m_rng = re.search(
            r"<startPosition[^>]*>(.*?)</startPosition>"
            r".*?<endPosition[^>]*>(.*?)</endPosition>",
            blk, re.I | re.S,
        )
        if m_rng:
            s, e = map(float, m_rng.groups())
            return np.linspace(s, e, npts)
        return None

    def _axis_or_none(*names: str) -> Optional[np.ndarray]:
        for nm in names:
            arr = _get_positions(nm)
            if arr is not None:
                return np.asarray(arr, dtype=float)
        return None

    omega = _axis_or_none("Omega", "Theta")
    two_theta = _axis_or_none(
        "Omega/2Theta", "Omega-2Theta", "Omega2Theta",
        "Theta/2Theta", "Theta-2Theta", "2Theta", "TwoTheta",
    )

    if omega is None and two_theta is None:
        omega = np.arange(npts, dtype=float) * 0.5
        two_theta = 2.0 * omega
    elif omega is None:
        omega = 0.5 * two_theta
    elif two_theta is None:
        two_theta = 2.0 * omega

    return {
        "omega": np.asarray(omega, dtype=float),
        "two_theta": np.asarray(two_theta, dtype=float),
        "y": y,
    }


# -----------------------------------------------------------------------
#  Utility helpers
# -----------------------------------------------------------------------

def peak_preserving_downsample(
    theta: np.ndarray, y: np.ndarray, target: int = 600
) -> np.ndarray:
    """Down-sample an XRR curve while preserving Kiessig fringes.

    Returns an index array.
    """
    theta = np.asarray(theta, float)
    y = np.asarray(y, float)
    n = theta.size
    if n <= target:
        return np.arange(n, dtype=int)

    k_uniform = max(2, target // 2)
    idx_uniform = np.linspace(0, n - 1, k_uniform, dtype=int)

    ly = np.log(np.clip(y, 1e-18, None))
    d2 = np.abs(np.convolve(ly, [1.0, -2.0, 1.0], mode="same"))
    k_curv = target - k_uniform
    idx_curv = np.argpartition(d2, -k_curv)[-k_curv:]

    idx = np.unique(np.sort(np.concatenate([idx_uniform, idx_curv])))
    if idx[0] != 0:
        idx[0] = 0
    if idx[-1] != n - 1:
        idx[-1] = n - 1
    return idx


def expand_stack(
    base_n: np.ndarray,
    base_k: np.ndarray,
    base_t: np.ndarray,
    base_s: np.ndarray,
    blocks: List[Tuple[str, int, int, int]],
    substrate: Dict[str, float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Expand base-layer arrays through repeat blocks into full stack arrays.

    Returns (n_full, k_full, d_full, sigma_full) including vacuum (top)
    and substrate (bottom).
    """
    nL = [1.0]
    kL = [0.0]
    tL = [0.0]
    sL = [0.0]
    for kind, i0, i1, rep in blocks:
        for _ in range(rep):
            nL += list(base_n[i0:i1])
            kL += list(base_k[i0:i1])
            tL += list(base_t[i0:i1])
            sL += list(base_s[i0:i1])
    nL.append(substrate["n"])
    kL.append(substrate["k"])
    tL.append(0.0)
    sL.append(substrate["s"])
    return (
        np.array(nL, float),
        np.array(kL, float),
        np.array(tL, float),
        np.array(sL, float),
    )


def normalize_periodicity(
    t_base: np.ndarray,
    blocks: List[Tuple[str, int, int, int]],
    d_targets: List[float],
    fixed_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Rescale layer thicknesses so that each repeat-block sums to the target period."""
    if not d_targets:
        return t_base
    out = t_base.copy()
    bidx = 0
    for kind, i0, i1, rep in blocks:
        if kind == "repeat":
            d0 = d_targets[bidx]
            seg = out[i0:i1]
            if fixed_mask is None:
                dcur = float(np.sum(seg))
                if dcur > 0:
                    out[i0:i1] *= d0 / dcur
            else:
                fseg = fixed_mask[i0:i1]
                d_fixed = float(np.sum(seg[fseg]))
                d_var = float(np.sum(seg[~fseg]))
                if d_var > 0 and d0 > d_fixed:
                    scale = (d0 - d_fixed) / d_var
                    out[i0:i1][~fseg] *= scale
            bidx += 1
    return out


def fit_xrr_residual(
    theta: np.ndarray,
    y_exp: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d_arr: np.ndarray,
    s_arr: np.ndarray,
    wavelength_nm: float,
    weights: Optional[np.ndarray] = None,
) -> Tuple[float, np.ndarray]:
    """Compute the weighted log-residual and the scaled simulated curve.

    Returns
    -------
    chi2 : float
        Mean weighted squared log-residual.
    y_calc : 1-D array
        Simulated curve after auto-scaling.
    """
    y_sim = parratt(theta, n_arr, k_arr, d_arr, s_arr, wavelength_nm)
    y_sim = np.maximum(y_sim, 1e-18)
    y_exp_c = np.maximum(y_exp, 1e-18)
    scale = np.exp(np.mean(np.log(y_exp_c) - np.log(y_sim)))
    y_calc = y_sim * scale
    r = np.log10(y_exp_c) - np.log10(y_calc)
    w = weights if weights is not None else np.ones_like(r)
    chi2 = float(np.mean(r * r * w))
    return chi2, y_calc
