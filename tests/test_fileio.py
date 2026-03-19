"""Tests for xross.fileio — layer model save/load, logging."""

import os
import tempfile

import pandas as pd
import pytest

from xross.fileio import (
    load_layer_model,
    log_message,
    save_layer_model,
    save_results_csv,
)


class TestSaveLoadLayerModel:
    def test_round_trip(self, tmp_path):
        fp = str(tmp_path / "model.csv")
        rows = [
            {"subroutine": "MoSi", "loop_count": "40",
             "params": ["Mo", "0.92", "0.006", "2.8", "5.0", "0.3"]},
            {"subroutine": "MoSi", "loop_count": "40",
             "params": ["Si", "1.0", "0.002", "4.1", "2.33", "0.3"]},
            {"subroutine": "Orphan", "loop_count": "",
             "params": ["Cap", "1.0", "0.0", "1.0", "2.0", "0.1"]},
        ]
        save_layer_model(fp, rows)
        loaded = load_layer_model(fp)
        assert len(loaded) == 3
        assert loaded[0]["subroutine"] == "MoSi"
        assert loaded[0]["loop_count"] == "40"
        assert loaded[0]["params"][0] == "Mo"
        assert loaded[2]["subroutine"] == "Orphan"

    def test_empty_model(self, tmp_path):
        fp = str(tmp_path / "empty.csv")
        save_layer_model(fp, [])
        loaded = load_layer_model(fp)
        assert len(loaded) == 0

    def test_missing_params_padded(self, tmp_path):
        fp = str(tmp_path / "short.csv")
        rows = [
            {"subroutine": "A", "loop_count": "1", "params": ["X"]},
            {"subroutine": "A", "loop_count": "1", "params": ["Y", "0.9", "0.01"]},
        ]
        save_layer_model(fp, rows)
        loaded = load_layer_model(fp)
        assert len(loaded) == 2
        # Shorter row should be padded
        assert len(loaded[0]["params"]) == len(loaded[1]["params"])


class TestSaveResultsCsv:
    def test_dataframe_saved(self, tmp_path):
        fp = str(tmp_path / "results.csv")
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        save_results_csv(fp, df)
        loaded = pd.read_csv(fp)
        assert list(loaded.columns) == ["x", "y"]
        assert len(loaded) == 3


class TestLogMessage:
    def test_format(self):
        line = log_message("test message")
        assert "test message" in line
        assert "/" in line  # timestamp contains /

    def test_writes_to_file(self, tmp_path):
        log_message("hello", str(tmp_path))
        log_file = tmp_path / "log.txt"
        assert log_file.exists()
        content = log_file.read_text()
        assert "hello" in content

    def test_appends(self, tmp_path):
        log_message("first", str(tmp_path))
        log_message("second", str(tmp_path))
        content = (tmp_path / "log.txt").read_text()
        assert "first" in content
        assert "second" in content
