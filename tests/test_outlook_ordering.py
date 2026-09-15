"""Archive enumeration order must not change model training or selection."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import compute_outlook as outlook


def test_shuffled_archive_has_identical_backtests_and_forecast(monkeypatch):
    series = [{"year": y, "month": m, "value": float((y - 2000) * 12 + m)}
              for y in range(2000, 2008) for m in range(1, 13)]
    calls = []
    class Model:
        def __init__(self, values, **kwargs):
            self.values = list(values)
            calls.append(self.values)
        def fit(self):
            return self
        def forecast(self, steps):
            return [self.values[-1]] * steps
    monkeypatch.setattr(outlook, "ARIMA", Model)
    targets, _ = outlook._target_window(2006, 6)
    expected = outlook._compute_district_outlook(series, targets, 2006, 6, 3, 2)
    expected_calls = calls[:]
    assert len(expected_calls) == 4  # three backtest origins and current forecast
    calls.clear()
    random.Random(42).shuffle(series)
    actual = outlook._compute_district_outlook(series, targets, 2006, 6, 3, 2)
    assert calls == expected_calls
    assert actual == expected
    assert all(values == sorted(values) for values in calls)
    assert max(calls[-1]) == float((2006 - 2000) * 12 + 6)  # no future inputs
