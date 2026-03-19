"""Tests for xross.xrr — XRDML loader, downsampling, stack expansion."""

import numpy as np
import pytest

from xross.xrr import (
    expand_stack,
    fit_xrr_residual,
    normalize_periodicity,
    peak_preserving_downsample,
)
from xross.core import parratt


class TestPeakPreservingDownsample:
    def test_short_array_unchanged(self):
        theta = np.linspace(0.1, 2.0, 50)
        y = np.random.rand(50)
        idx = peak_preserving_downsample(theta, y, target=100)
        assert len(idx) == 50

    def test_long_array_downsampled(self):
        theta = np.linspace(0.1, 5.0, 2000)
        y = np.exp(-theta) * np.sin(10 * theta) ** 2 + 1e-6
        idx = peak_preserving_downsample(theta, y, target=600)
        assert len(idx) <= 700
        assert idx[0] == 0
        assert idx[-1] == 1999


class TestExpandStack:
    def test_single_block(self):
        base_n = np.array([0.92, 1.0])
        base_k = np.array([0.006, 0.002])
        base_t = np.array([2.8, 4.1])
        base_s = np.array([0.3, 0.3])
        blocks = [("repeat", 0, 2, 3)]
        sub = {"n": 0.999, "k": 0.0, "s": 0.0}
        n, k, t, s = expand_stack(base_n, base_k, base_t, base_s, blocks, sub)
        # vacuum + 3×(Mo,Si) + substrate = 1 + 6 + 1 = 8
        assert len(n) == 8
        assert n[0] == 1.0  # vacuum
        assert n[-1] == pytest.approx(0.999)  # substrate


class TestNormalizePeriodicity:
    def test_rescaling(self):
        t = np.array([2.0, 3.0])
        blocks = [("repeat", 0, 2, 10)]
        d_targets = [10.0]  # want period = 10 nm
        result = normalize_periodicity(t, blocks, d_targets)
        assert np.sum(result) == pytest.approx(10.0)


class TestFitXrrResidual:
    def test_perfect_fit(self):
        """Fitting the model to itself should give chi2 ≈ 0."""
        theta = np.linspace(0.2, 3.0, 200)
        n_arr = np.array([1.0, 1.0 - 1e-5, 1.0 - 7.6e-6])
        k_arr = np.array([0.0, 1e-7, 1.7e-7])
        d_arr = np.array([0.0, 15.0, 0.0])
        s_arr = np.array([0.0, 0.3, 0.0])
        y_sim = parratt(theta, n_arr, k_arr, d_arr, s_arr, 0.15418)
        chi2, y_calc = fit_xrr_residual(
            theta, y_sim, n_arr, k_arr, d_arr, s_arr, 0.15418
        )
        assert chi2 < 1e-10
