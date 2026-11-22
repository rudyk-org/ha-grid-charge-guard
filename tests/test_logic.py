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
                    stable_for=0, since_increase=0)
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
