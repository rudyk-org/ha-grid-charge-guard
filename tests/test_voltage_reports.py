"""Regression tests for slow Luxpower voltage reporting (20s cadence)."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys

p = Path(__file__).resolve().parents[1] / "custom_components/grid_charge_guard/logic.py"
spec = spec_from_file_location("grid_charge_logic_v024", p)
logic = module_from_spec(spec)
sys.modules[spec.name] = logic
spec.loader.exec_module(logic)


def case(**kwargs):
    defaults = dict(voltage=230, average_voltage=230, sustained_low=False, current=50,
                    user_max=100, min_current=10, losses=0, derate_active=False,
                    stable_for=0, since_increase=0, since_voltage_decrease=999)
    return logic.decide_current(**(defaults | kwargs))


def test_single_191v_sample_does_not_drop_to_floor():
    assert case(voltage=191, average_voltage=230, current=65,
                critical_samples=1).target == 65
    assert case(voltage=191, average_voltage=230, current=65,
                critical_samples=1).mode == 'voltage_dip'


def test_two_distinct_191v_samples_use_one_severe_step():
    assert case(voltage=191, average_voltage=230, current=65,
                critical_samples=2).target == 55
    assert case(voltage=191, average_voltage=230, current=65,
                critical_samples=2, since_voltage_decrease=20).target == 65


def test_three_distinct_191v_samples_reach_configured_floor():
    assert case(voltage=191, average_voltage=230, current=65,
                min_current=15, critical_samples=3).target == 15


def test_extreme_under_185v_act_immediately():
    assert case(voltage=184.9, average_voltage=230, current=80,
                critical_samples=1, min_current=10).target == 10


def test_voltage_reports_deduplicated_with_20s_sensor_poll():
    o = logic.VoltageObservations()
    assert o.observe(100, 191)
    assert not o.observe(100, 191)  # 10 s timer got same sensor report
    assert o.critical_samples == 1
    assert not o.sustained_low()
    assert o.observe(120, 191)
    assert o.critical_samples == 2
    assert o.sustained_low()
    assert not o.observe(120, 191)
    assert o.critical_samples == 2
    assert o.observe(140, 191)
    assert o.critical_samples == 3
    assert o.observe(160, 230)
    assert o.critical_samples == 0
    assert o.low_samples == 0


def test_averaging_uses_distinct_sensor_reports():
    o = logic.VoltageObservations()
    w = logic.VoltageWindow(window_seconds=180, warmup_seconds=120, min_samples=8)
    for t in range(0, 161, 10):
        # 20s voltage cadence; 10s controller poll
        report_at = (t // 20) * 20
        if o.observe(report_at, 230):
            average = w.add(report_at, 230)
    assert len(w.samples) == 9
    assert average == 230
