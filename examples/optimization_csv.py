"""
examples/optimization_csv.py — Example: multi-objective process optimisation.

Demonstrates the XROSS Python API for training a surrogate model from
CSV data and running NSGA-II to find Pareto-optimal conditions.

Usage:
    python examples/optimization_csv.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from xross.optimize import OptimizationProblem, nsga2

# --- Generate synthetic process data ---
# Imagine a thin-film deposition with 3 control parameters:
#   x1 = Temperature (°C)
#   x2 = Pressure (Pa)
#   x3 = Time (min)
# and 2 quality outputs:
#   y1 = Roughness (nm)  → minimise
#   y2 = Thickness (nm)  → target = maximise

np.random.seed(42)
n_samples = 50
x1 = np.random.uniform(200, 600, n_samples)
x2 = np.random.uniform(0.1, 10, n_samples)
x3 = np.random.uniform(5, 60, n_samples)

# Synthetic relationships
roughness = 0.5 + 0.002 * (x1 - 400)**2 / 100 + 0.3 * np.log(x2 + 1) + np.random.normal(0, 0.2, n_samples)
thickness = 10 + 0.05 * x1 + 2.0 * x3**0.5 - 0.5 * x2 + np.random.normal(0, 1.0, n_samples)

df = pd.DataFrame({
    "Temperature": x1, "Pressure": x2, "Time": x3,
    "Roughness": roughness, "Thickness": thickness,
})
print("Synthetic training data:")
print(df.describe().to_string())
print()

# --- Train surrogate models (using scikit-learn) ---
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

x_cols = ["Temperature", "Pressure", "Time"]
y_cols = ["Roughness", "Thickness"]

X = df[x_cols].values
scalers_x, scalers_y, models = {}, {}, {}

for yc in y_cols:
    y = df[yc].values
    sx = StandardScaler().fit(X)
    sy = StandardScaler().fit(y.reshape(-1, 1))
    Xs = sx.transform(X)
    ys = sy.transform(y.reshape(-1, 1)).ravel()
    m = RandomForestRegressor(n_estimators=100, random_state=0)
    m.fit(Xs, ys)
    scalers_x[yc] = sx
    scalers_y[yc] = sy
    models[yc] = m
    print(f"  {yc}: R² = {m.score(Xs, ys):.4f}")

# --- Define optimisation problem ---
lo = np.array([200, 0.1, 5])
hi = np.array([600, 10, 60])
directions = np.array([1.0, -1.0])  # minimise roughness, maximise thickness

def evaluate(pop):
    obj = np.zeros((pop.shape[0], 2))
    for j, yc in enumerate(y_cols):
        Xs = scalers_x[yc].transform(pop)
        ys = models[yc].predict(Xs)
        obj[:, j] = scalers_y[yc].inverse_transform(ys.reshape(-1, 1)).ravel()
    return obj

prob = OptimizationProblem(
    n_var=3, n_obj=2,
    lower_bounds=lo, upper_bounds=hi,
    directions=directions,
    evaluate=evaluate,
)

# --- Run NSGA-II ---
print("\nRunning NSGA-II (pop=80, gen=150)...")
pareto_x, pareto_obj = nsga2(prob, n_pop=80, n_gen=150, seed=42)
print(f"  Pareto front: {len(pareto_x)} solutions")

# --- Display results ---
pareto_df = pd.DataFrame(
    np.hstack([pareto_x, pareto_obj]),
    columns=x_cols + [f"{c} (predicted)" for c in y_cols],
)
print("\nTop 5 solutions (sorted by Roughness):")
print(pareto_df.sort_values("Roughness (predicted)").head().to_string(index=False))

# --- Plot Pareto front ---
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(
    pareto_obj[:, 0], pareto_obj[:, 1],
    s=40, alpha=0.7, edgecolors="black", linewidth=0.5,
)
ax.set_xlabel("Roughness (nm) — minimise →")
ax.set_ylabel("Thickness (nm) — ← maximise")
ax.set_title("Pareto Front: Roughness vs Thickness")
ax.grid(True, alpha=0.3)
fig.tight_layout()
plt.savefig("optimization_pareto.png", dpi=150)
plt.show()
