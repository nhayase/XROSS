"""
xross.fileio — File I/O for XROSS layer models and results.

Handles serialisation of layer stacks to/from CSV and provides
logging utilities.
"""

from __future__ import annotations

import csv
import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

__all__ = [
    "save_layer_model",
    "load_layer_model",
    "save_results_csv",
    "log_message",
]


def save_layer_model(
    filepath: str,
    rows: List[Dict[str, Any]],
) -> None:
    """Save a layer model to CSV.

    Parameters
    ----------
    filepath : str
        Destination path.
    rows : list of dict
        Each dict has ``"subroutine"``, ``"loop_count"``, and
        ``"params"`` (list of str).
    """
    max_param = max((len(r.get("params", [])) for r in rows), default=0)
    header = ["Subroutine", "Loop Count"] + [f"Param{i+1}" for i in range(max_param)]
    fixed = []
    for r in rows:
        row = [r.get("subroutine", "Orphan"), str(r.get("loop_count", ""))]
        row += r.get("params", [])
        row += [""] * (len(header) - len(row))
        fixed.append(row[: len(header)])
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(fixed)


def load_layer_model(filepath: str) -> List[Dict[str, Any]]:
    """Load a layer model from CSV.

    Returns
    -------
    list of dict
        Each dict has ``"subroutine"`` (str), ``"loop_count"`` (str),
        ``"params"`` (list of str).
    """
    df = pd.read_csv(filepath, dtype=str).fillna("")
    result = []
    for _, row in df.iterrows():
        result.append(
            {
                "subroutine": row["Subroutine"],
                "loop_count": row["Loop Count"],
                "params": [v for v in row.iloc[2:].values],
            }
        )
    return result


def save_results_csv(
    filepath: str,
    dataframe: pd.DataFrame,
) -> None:
    """Save a results DataFrame to CSV."""
    dataframe.to_csv(filepath, index=False)


def log_message(message: str, log_dir: Optional[str] = None) -> str:
    """Format and optionally write a timestamped log message.

    Returns the formatted string.
    """
    ts = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    line = f"{ts} {message}\n"
    if log_dir:
        log_path = os.path.join(log_dir, "log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    return line
