"""Tests for xross.optimize — NSGA-II, non-dominated sorting, crowding distance."""

import numpy as np
import pytest

from xross.optimize import (
    OptimizationProblem,
    crowding_distance,
    fast_nondominated_sort,
    nsga2,
)


class TestNonDominatedSort:
    def test_single_point(self):
        obj = np.array([[1.0, 2.0]])
        fronts = fast_nondominated_sort(obj)
        assert len(fronts) == 1
        assert fronts[0] == [0]

    def test_two_non_dominated(self):
        obj = np.array([[1.0, 3.0], [2.0, 1.0]])
        fronts = fast_nondominated_sort(obj)
        assert len(fronts) == 1
        assert set(fronts[0]) == {0, 1}

    def test_dominated_point(self):
        obj = np.array([[1.0, 1.0], [2.0, 2.0]])
        fronts = fast_nondominated_sort(obj)
        assert len(fronts) == 2
        assert fronts[0] == [0]
        assert fronts[1] == [1]


class TestCrowdingDistance:
    def test_two_points_infinite(self):
        obj = np.array([[1.0, 3.0], [2.0, 1.0]])
        cd = crowding_distance(obj, [0, 1])
        assert np.all(np.isinf(cd))

    def test_three_points(self):
        obj = np.array([[1.0, 3.0], [1.5, 2.0], [2.0, 1.0]])
        cd = crowding_distance(obj, [0, 1, 2])
        assert np.isinf(cd[0]) and np.isinf(cd[2])
        assert np.isfinite(cd[1]) and cd[1] > 0


class TestNSGA2:
    def test_single_objective_minimise(self):
        """Minimise f(x) = (x-3)^2 on [0, 10]."""
        def evaluate(pop):
            return (pop[:, 0:1] - 3.0) ** 2

        prob = OptimizationProblem(
            n_var=1, n_obj=1,
            lower_bounds=np.array([0.0]),
            upper_bounds=np.array([10.0]),
            directions=np.array([1.0]),
            evaluate=evaluate,
        )
        px, po = nsga2(prob, n_pop=30, n_gen=50, seed=0)
        best_x = px[np.argmin(po[:, 0]), 0]
        assert best_x == pytest.approx(3.0, abs=0.5)

    def test_two_objective(self):
        """ZDT1-like: conflicting objectives → Pareto front."""
        def evaluate(pop):
            f1 = pop[:, 0]
            g = 1.0 + 9.0 * np.mean(pop[:, 1:], axis=1)
            f2 = g * (1.0 - np.sqrt(f1 / g))
            return np.column_stack([f1, f2])

        prob = OptimizationProblem(
            n_var=3, n_obj=2,
            lower_bounds=np.zeros(3),
            upper_bounds=np.ones(3),
            directions=np.array([1.0, 1.0]),
            evaluate=evaluate,
        )
        px, po = nsga2(prob, n_pop=50, n_gen=100, seed=42)
        assert px.shape[0] > 1  # multiple Pareto solutions
        assert po.shape[1] == 2

    def test_maximise_direction(self):
        """Maximise f(x) = -x^2 → optimal at x=0."""
        def evaluate(pop):
            return -(pop ** 2)

        prob = OptimizationProblem(
            n_var=1, n_obj=1,
            lower_bounds=np.array([-5.0]),
            upper_bounds=np.array([5.0]),
            directions=np.array([-1.0]),  # maximise
            evaluate=evaluate,
        )
        px, po = nsga2(prob, n_pop=30, n_gen=50, seed=0)
        best_x = px[np.argmax(po[:, 0]), 0]
        assert abs(best_x) < 1.0
