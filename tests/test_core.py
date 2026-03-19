"""Tests for xross.core — reflectivity, Parratt, nk parsing."""

import math
import os
import tempfile

import numpy as np
import pytest

from xross.core import (
    Layer,
    build_stack,
    interp_nk,
    parse_nk_file,
    parratt,
    reflectivity_matrix,
)


# -----------------------------------------------------------------------
#  Layer / build_stack
# -----------------------------------------------------------------------

class TestLayer:
    def test_as_tuple(self):
        lay = Layer("Mo", n=0.92, k=0.006, thickness_nm=2.8, roughness_nm=0.3)
        assert lay.as_tuple() == (0.92, 0.006, 2.8, 0.3)

    def test_repr(self):
        lay = Layer("Si")
        assert "Si" in repr(lay)


class TestBuildStack:
    def test_single_repeat(self):
        layers = [Layer("A", n=1.0, k=0.0, thickness_nm=3.0)]
        stack = build_stack(layers, repeat=1)
        assert len(stack) == 1

    def test_multi_repeat(self):
        layers = [Layer("A"), Layer("B")]
        stack = build_stack(layers, repeat=3)
        assert len(stack) == 6

    def test_with_cap(self):
        layers = [Layer("A")]
        cap = Layer("Cap")
        stack = build_stack(layers, repeat=2, cap=cap)
        assert len(stack) == 3  # 2×A + cap


# -----------------------------------------------------------------------
#  reflectivity_matrix
# -----------------------------------------------------------------------

class TestReflectivityMatrix:
    def test_vacuum_only(self):
        """Two vacuum layers → R should be 0 (no interface contrast)."""
        stack = [(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)]
        R, phase = reflectivity_matrix(stack, wavelength_nm=13.5, angle_deg=6.0)
        assert R == pytest.approx(0.0, abs=1e-10)

    def test_single_interface_normal_incidence(self):
        """Vacuum/glass interface at normal incidence → Fresnel formula."""
        n_glass = 1.5
        stack = [(1.0, 0.0, 0.0, 0.0), (n_glass, 0.0, 0.0, 0.0)]
        R, _ = reflectivity_matrix(stack, wavelength_nm=500.0, angle_deg=0.01)
        R_fresnel = ((1.0 - n_glass) / (1.0 + n_glass)) ** 2
        assert R == pytest.approx(R_fresnel, rel=0.05)

    def test_reflectivity_bounded(self):
        """Reflectivity should be in [0, 1]."""
        stack = [(1.0, 0.0, 0.0, 0.0), (0.92, 0.006, 2.8, 0.3),
                 (1.0, 0.0, 4.1, 0.3), (0.92, 0.006, 0.0, 0.0)]
        R, _ = reflectivity_matrix(stack, wavelength_nm=13.5, angle_deg=6.0)
        assert 0.0 <= R <= 1.0

    def test_multilayer_peak(self):
        """A Mo/Si multilayer near 13.5 nm should show measurable reflectivity."""
        Mo = (0.9212, 0.00643, 2.8, 0.3)
        Si = (0.9999, 0.00183, 4.1, 0.3)
        stack = [(1.0, 0.0, 0.0, 0.0)] + [Mo, Si] * 40 + [Si]
        R, _ = reflectivity_matrix(stack, wavelength_nm=13.5, angle_deg=6.0)
        assert R > 0.01  # should be significantly > 0


# -----------------------------------------------------------------------
#  Parratt recursion
# -----------------------------------------------------------------------

class TestParratt:
    def test_single_interface(self):
        """Single vacuum/substrate interface should give smooth monotone curve."""
        theta = np.linspace(0.1, 5.0, 100)
        n_arr = np.array([1.0, 1.0 - 7.6e-6])
        k_arr = np.array([0.0, 1.7e-7])
        d_arr = np.array([0.0, 0.0])
        s_arr = np.array([0.0, 0.0])
        R = parratt(theta, n_arr, k_arr, d_arr, s_arr, wavelength_nm=0.15418)
        assert R.shape == theta.shape
        assert np.all(R >= 0)
        assert np.all(np.isfinite(R))
        # At grazing angles R should approach 1, at higher angles decrease
        assert R[0] > R[-1]

    def test_thin_film_fringes(self):
        """A thin film should produce Kiessig fringes (oscillations)."""
        theta = np.linspace(0.2, 3.0, 500)
        n_arr = np.array([1.0, 1.0 - 1e-5, 1.0 - 7.6e-6])
        k_arr = np.array([0.0, 1e-7, 1.7e-7])
        d_arr = np.array([0.0, 20.0, 0.0])  # 20 nm film
        s_arr = np.array([0.0, 0.0, 0.0])
        R = parratt(theta, n_arr, k_arr, d_arr, s_arr, wavelength_nm=0.15418)
        # Check that fringes exist (R is not monotone)
        diffs = np.diff(R)
        sign_changes = np.sum(np.diff(np.sign(diffs)) != 0)
        assert sign_changes > 2  # at least a few oscillations

    def test_roughness_reduces_reflectivity(self):
        """Adding roughness should reduce peak reflectivity."""
        theta = np.array([0.5])
        n_arr = np.array([1.0, 1.0 - 7.6e-6])
        k_arr = np.array([0.0, 0.0])
        d_arr = np.array([0.0, 0.0])
        R_smooth = parratt(theta, n_arr, k_arr, d_arr, np.array([0.0, 0.0]), 0.15418)
        R_rough = parratt(theta, n_arr, k_arr, d_arr, np.array([0.0, 0.5]), 0.15418)
        assert R_rough[0] <= R_smooth[0]


# -----------------------------------------------------------------------
#  nk file parsing
# -----------------------------------------------------------------------

class TestParseNkFile:
    def test_basic_file(self, tmp_path):
        nk_file = tmp_path / "test.nk"
        nk_file.write_text("100.0  0.95  0.01\n200.0  0.98  0.005\n")
        lam, n, k = parse_nk_file(str(nk_file))
        assert len(lam) == 2
        assert lam[0] == pytest.approx(10.0)  # 100 Å → 10 nm
        assert lam[1] == pytest.approx(20.0)
        assert n[0] == pytest.approx(0.95)
        assert k[1] == pytest.approx(0.005)

    def test_comments_skipped(self, tmp_path):
        nk_file = tmp_path / "comments.nk"
        nk_file.write_text("# header\n100.0  0.95  0.01\n// skip\n200.0  0.98  0.005\n")
        lam, n, k = parse_nk_file(str(nk_file))
        assert len(lam) == 2

    def test_empty_file_raises(self, tmp_path):
        nk_file = tmp_path / "empty.nk"
        nk_file.write_text("# only comments\n")
        with pytest.raises(ValueError, match="No numeric rows"):
            parse_nk_file(str(nk_file))

    def test_sorted_and_unique(self, tmp_path):
        nk_file = tmp_path / "unsorted.nk"
        nk_file.write_text("200 0.98 0.005\n100 0.95 0.01\n200 0.97 0.006\n")
        lam, n, k = parse_nk_file(str(nk_file))
        assert np.all(np.diff(lam) > 0)  # sorted
        assert len(lam) == 2  # duplicates removed


class TestInterpNk:
    def test_interpolation(self):
        lam = np.array([10.0, 20.0, 30.0])
        n = np.array([0.9, 0.95, 0.98])
        k = np.array([0.01, 0.005, 0.002])
        target = np.array([15.0])
        ni, ki = interp_nk(target, lam, n, k)
        assert ni[0] == pytest.approx(0.925)
        assert ki[0] == pytest.approx(0.0075)
