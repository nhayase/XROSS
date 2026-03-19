"""
xross.optimize — Multi-objective optimisation engine.

Provides NSGA-II genetic algorithm for multi-parameter, multi-objective
optimisation of thin-film process conditions.  Designed to work with
arbitrary CSV data (any number of explanatory / objective variables).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

__all__ = [
    "OptimizationProblem",
    "nsga2",
    "fast_nondominated_sort",
    "crowding_distance",
]


# -----------------------------------------------------------------------
#  Problem description
# -----------------------------------------------------------------------

@dataclass
class OptimizationProblem:
    """Specification of a multi-objective optimisation problem.

    Attributes
    ----------
    n_var : int
        Number of decision (explanatory) variables.
    n_obj : int
        Number of objectives.
    lower_bounds : 1-D array of shape (n_var,)
    upper_bounds : 1-D array of shape (n_var,)
    directions : 1-D array of shape (n_obj,)
        ``+1`` for minimise, ``-1`` for maximise.
    evaluate : callable (pop) -> obj
        Maps ``(n_pop, n_var)`` to ``(n_pop, n_obj)`` **raw** objective
        values.  The NSGA-II driver applies the sign convention internally.
    """

    n_var: int
    n_obj: int
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    directions: np.ndarray
    evaluate: Callable[[np.ndarray], np.ndarray]


# -----------------------------------------------------------------------
#  NSGA-II components
# -----------------------------------------------------------------------

def fast_nondominated_sort(obj: np.ndarray) -> List[List[int]]:
    """Return successive Pareto fronts (indices) for a *minimisation* problem."""
    n = obj.shape[0]
    domination_count = np.zeros(n, dtype=int)
    dominated_set: List[List[int]] = [[] for _ in range(n)]
    fronts: List[List[int]] = [[]]
    for i in range(n):
        for j in range(i + 1, n):
            if np.all(obj[i] <= obj[j]) and np.any(obj[i] < obj[j]):
                dominated_set[i].append(j)
                domination_count[j] += 1
            elif np.all(obj[j] <= obj[i]) and np.any(obj[j] < obj[i]):
                dominated_set[j].append(i)
                domination_count[i] += 1
        if domination_count[i] == 0:
            fronts[0].append(i)
    k = 0
    while fronts[k]:
        nxt: List[int] = []
        for i in fronts[k]:
            for j in dominated_set[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    nxt.append(j)
        k += 1
        fronts.append(nxt)
    return [f for f in fronts if f]


def crowding_distance(obj: np.ndarray, front: List[int]) -> np.ndarray:
    """Compute crowding distance for individuals in *front*."""
    n = len(front)
    if n <= 2:
        return np.full(n, np.inf)
    dist = np.zeros(n)
    for m in range(obj.shape[1]):
        vals = obj[front, m]
        order = np.argsort(vals)
        dist[order[0]] = np.inf
        dist[order[-1]] = np.inf
        rng = vals[order[-1]] - vals[order[0]]
        if rng < 1e-12:
            continue
        for i in range(1, n - 1):
            dist[order[i]] += (vals[order[i + 1]] - vals[order[i - 1]]) / rng
    return dist


# -----------------------------------------------------------------------
#  NSGA-II main loop
# -----------------------------------------------------------------------

def nsga2(
    problem: OptimizationProblem,
    *,
    n_pop: int = 100,
    n_gen: int = 200,
    seed: int = 42,
    callback: Optional[Callable[[int, np.ndarray, np.ndarray], None]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Run NSGA-II and return the Pareto-optimal decision vectors and objectives.

    Parameters
    ----------
    problem : OptimizationProblem
    n_pop, n_gen : int
        Population size and number of generations.
    seed : int
        Random seed.
    callback : callable or None
        ``callback(gen, pareto_x, pareto_obj_raw)`` called periodically.

    Returns
    -------
    pareto_x : 2-D array (n_pareto, n_var)
    pareto_obj : 2-D array (n_pareto, n_obj)
        Raw objective values (before sign flip).
    """
    rng = np.random.default_rng(seed)
    lo, hi = problem.lower_bounds, problem.upper_bounds
    dirs = problem.directions  # +1 min, -1 max

    pop = rng.uniform(lo, hi, size=(n_pop, problem.n_var))
    obj_raw = problem.evaluate(pop)
    obj = obj_raw * dirs[None, :]  # internal: always minimise

    eta_c, eta_m, p_mut = 20, 20, 0.2

    def _sbx_pm(parents: np.ndarray) -> np.ndarray:
        n, d = parents.shape
        children = parents.copy()
        for i in range(0, n - 1, 2):
            if rng.random() < 0.9:
                u = rng.random(d)
                beta = np.where(
                    u <= 0.5,
                    (2 * u) ** (1.0 / (eta_c + 1)),
                    (1.0 / (2 * (1 - u))) ** (1.0 / (eta_c + 1)),
                )
                c1 = 0.5 * ((1 + beta) * parents[i] + (1 - beta) * parents[i + 1])
                c2 = 0.5 * ((1 - beta) * parents[i] + (1 + beta) * parents[i + 1])
                children[i] = np.clip(c1, lo, hi)
                children[i + 1] = np.clip(c2, lo, hi)
        for i in range(n):
            for j in range(d):
                if rng.random() < p_mut:
                    delta = hi[j] - lo[j]
                    if delta < 1e-15:
                        continue
                    u = rng.random()
                    if u < 0.5:
                        dq = (2 * u) ** (1.0 / (eta_m + 1)) - 1
                    else:
                        dq = 1 - (2 * (1 - u)) ** (1.0 / (eta_m + 1))
                    children[i, j] = np.clip(children[i, j] + dq * delta, lo[j], hi[j])
        return children

    for gen in range(n_gen):
        fronts = fast_nondominated_sort(obj)
        rank = np.zeros(n_pop, dtype=int)
        crowd = np.zeros(n_pop, dtype=float)
        for fi, front in enumerate(fronts):
            for idx in front:
                rank[idx] = fi
            cd = crowding_distance(obj, front)
            for k_i, idx in enumerate(front):
                crowd[idx] = cd[k_i]

        # Tournament selection
        sel = np.empty_like(pop)
        for i in range(n_pop):
            a, b = rng.integers(0, n_pop, 2)
            if rank[a] < rank[b]:
                sel[i] = pop[a]
            elif rank[a] > rank[b]:
                sel[i] = pop[b]
            elif crowd[a] > crowd[b]:
                sel[i] = pop[a]
            else:
                sel[i] = pop[b]

        children = _sbx_pm(sel)
        obj_ch_raw = problem.evaluate(children)
        obj_ch = obj_ch_raw * dirs[None, :]

        combined_pop = np.vstack([pop, children])
        combined_obj = np.vstack([obj, obj_ch])
        fronts_all = fast_nondominated_sort(combined_obj)

        new_pop, new_obj = [], []
        for front in fronts_all:
            if len(new_pop) + len(front) <= n_pop:
                for idx in front:
                    new_pop.append(combined_pop[idx])
                    new_obj.append(combined_obj[idx])
            else:
                cd = crowding_distance(combined_obj, front)
                order = np.argsort(-cd)
                remain = n_pop - len(new_pop)
                for k_i in order[:remain]:
                    new_pop.append(combined_pop[front[k_i]])
                    new_obj.append(combined_obj[front[k_i]])
                break

        pop = np.array(new_pop)
        obj = np.array(new_obj)

        if callback and (gen % max(1, n_gen // 10) == 0 or gen == n_gen - 1):
            bf = fast_nondominated_sort(obj)[0]
            callback(gen, pop[bf], (obj[bf] * dirs[None, :]))  # raw values

    best_front = fast_nondominated_sort(obj)[0]
    return pop[best_front], obj[best_front] * dirs[None, :]  # raw obj values
