from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "custom_components/grid_charge_guard/logic.py"
spec = spec_from_file_location("logic", p)
logic = module_from_spec(spec)
import sys
sys.modules[spec.name] = logic
spec.loader.exec_module(logic)


def case(**kwargs):
    defaults = dict(voltage=230, current=50, user_max=100,
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
    assert case(voltage=200, current=50).target == 40
    assert case(voltage=194, current=50).target == 10


def test_recovery_waits_five_minutes():
    assert case(stable_for=299, since_increase=999).target == 50
    assert case(stable_for=300, since_increase=300).target == 55


def test_never_exceeds_user_max():
    assert case(current=100, user_max=60).target == 60


def test_moderate_voltage_initial_drop_is_five_amps():
    assert case(voltage=210, current=50, since_voltage_decrease=30).target == 45


def test_moderate_voltage_reduction_waits_thirty_seconds():
    assert case(voltage=210, current=45, since_voltage_decrease=10).target == 45
    assert case(voltage=214.9, current=45, since_voltage_decrease=29.9).target == 45
    assert case(voltage=210, current=45, since_voltage_decrease=30).target == 40


def test_serious_voltage_sag_bypasses_moderate_throttle():
    assert case(voltage=200, current=50, since_voltage_decrease=1).target == 40
    assert case(voltage=194, current=50, since_voltage_decrease=1).target == 10


def test_grid_outage_cap_is_immediate_despite_moderate_throttle():
    assert case(voltage=210, current=80, losses=2, since_voltage_decrease=0).target == 50
    assert case(voltage=210, current=80, losses=3, since_voltage_decrease=0).target == 10


def test_just_above_moderate_band_does_not_decrease():
    assert case(voltage=215, current=50, since_voltage_decrease=999).target == 50
