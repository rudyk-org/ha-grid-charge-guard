from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components/grid_charge_guard/logic.py"
spec = spec_from_file_location("logic", p)
logic = module_from_spec(spec)
import sys
sys.modules[spec.name] = logic
spec.loader.exec_module(logic)


def case(**kwargs):
    defaults = dict(voltage=230, average_voltage=230, sustained_low=False, current=50, user_max=100,
                    min_current=10, losses=0, derate_active=False,
                    stable_for=0, since_increase=0,
                    since_voltage_decrease=999)
    return logic.decide_current(**(defaults | kwargs))


def test_one_outage_only_logged():
    assert case(losses=1).target == 50


def test_two_outages_cap_to_fifty():
    assert case(losses=2, current=80).target == 50


def test_three_outages_minimum():
    assert case(losses=3, current=80).target == 10


def test_cooldown_holds_minimum():
    assert case(derate_active=True, current=80).target == 10


def test_low_voltage_reduces_fast():
    assert case(voltage=200, current=50, sustained_low=True).target == 40
    assert case(voltage=194, current=50).target == 10


def test_recovery_waits_five_minutes():
    assert case(stable_for=119, since_increase=999).target == 50
    assert case(stable_for=120, since_increase=180).target == 55


def test_never_exceeds_user_max():
    assert case(current=100, user_max=60).target == 60


def test_short_dip_ignored_when_average_is_high():
    assert case(voltage=210, average_voltage=229, current=50,
                since_voltage_decrease=999).target == 50


def test_low_average_derate_is_rate_limited():
    assert case(voltage=228, average_voltage=210, current=50,
                since_voltage_decrease=119).target == 50
    assert case(voltage=228, average_voltage=210, current=50,
                since_voltage_decrease=120).target == 45
    assert case(voltage=228, average_voltage=204, current=50,
                since_voltage_decrease=45).target == 40


def test_stale_or_insufficient_average_never_increases():
    assert case(average_voltage=None, stable_for=999, since_increase=999).target == 50
    assert case(average_voltage=None).mode == "averaging"


def test_serious_voltage_sag_bypasses_filter():
    assert case(voltage=200, average_voltage=230, sustained_low=True,
                since_voltage_decrease=30).target == 40
    assert case(voltage=200, average_voltage=230, sustained_low=False,
                since_voltage_decrease=30).target == 50
    assert case(voltage=194, average_voltage=230,
                since_voltage_decrease=1).target == 10


def test_grid_loss_caps_override_average():
    assert case(voltage=230, average_voltage=None, current=80, losses=2,
                since_voltage_decrease=0).target == 50
    assert case(voltage=230, average_voltage=230, current=80, losses=3,
                since_voltage_decrease=0).target == 10


def test_hysteresis_on_mean_recovery_band():
    assert case(voltage=216, average_voltage=219, current=50,
                stable_for=999, since_increase=999).target == 50
    assert case(voltage=225, average_voltage=220, current=50,
                stable_for=120, since_increase=180).target == 55


def test_voltage_window_warmup_and_drop_old_samples():
    w = logic.VoltageWindow(window_seconds=180, warmup_seconds=120, min_samples=8)
    assert all(w.add(t, 230) is None for t in range(0, 120, 10))
    assert w.add(120, 220) == round((12*230+220)/13, 2)
    assert w.add(330, 210) is None  # Old samples expired; warm up again.


def test_voltage_window_zero_is_not_smoothed():
    w = logic.VoltageWindow()
    for t in range(0, 130, 10):
        avg = w.add(t, 230)
    assert avg == 230
    assert w.add(130, 0) is None  # phase selector transfer
    assert w.add(160, 230) is None
    assert w.samples[0] == (160, 230)


def test_invalid_voltage_does_not_authorize_charge_ramp():
    w = logic.VoltageWindow()
    assert w.add(0, float('nan')) is None
    assert w.add(10, 500) is None
    assert not w.samples


def test_dont_ramp_up_during_a_brief_raw_dip():
    assert case(voltage=210, average_voltage=230, current=50,
                stable_for=120, since_increase=180).target == 50
