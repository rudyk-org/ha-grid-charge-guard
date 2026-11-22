"""Test event notifications without requiring Home Assistant in the test runner."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/grid_charge_guard'
PKG = 'grid_charge_guard_test'
if PKG not in sys.modules:
    mod = types.ModuleType(PKG)
    mod.__path__ = [str(ROOT)]
    sys.modules[PKG] = mod

spec = importlib.util.spec_from_file_location(f'{PKG}.reporter', ROOT / 'reporter.py')
reporter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reporter
spec.loader.exec_module(reporter)

class Bus:
    def __init__(self):
        self.events = []
    def async_fire(self, name, data):
        self.events.append((name, data))

class Services:
    def __init__(self):
        self.calls = []
    async def async_call(self, domain, service, data, *, target=None, blocking=False):
        self.calls.append((domain, service, data, target, blocking))

class Controller:
    def __init__(self, notify='notify.test'):
        self.enabled = True
        self.current_entity = 'number.test_ac_current'
        self.entry = types.SimpleNamespace(options={'notify_entity': notify} if notify else {})
        self.hass = types.SimpleNamespace(bus=Bus(), services=Services())
        self.updated = 0
    def _notify(self):
        self.updated += 1


def test_routine_current_steps_are_logged_but_do_not_notify():
    c = Controller()
    r = reporter.EventReporter(c)
    asyncio.run(r.emit('current_requested', '50 -> 45 A', previous=50, target=45))
    assert len(c.hass.bus.events) == 1
    assert c.hass.services.calls == []
    assert r.last_event['target'] == 45


def test_alert_sends_a_message_through_notify_entity():
    c = Controller()
    r = reporter.EventReporter(c)
    asyncio.run(r.emit('grid_loss_2', '2 losses', severity='warning', notify=True))
    assert len(c.hass.services.calls) == 1
    domain, service, data, target, blocking = c.hass.services.calls[0]
    assert (domain, service) == ('notify', 'send_message')
    assert target == {'entity_id': 'notify.test'}
    assert '2 losses' in data['message']
    assert r.recovery_needed is True


def test_alert_cooldown_prevents_duplicate_telegram_spam():
    c = Controller()
    r = reporter.EventReporter(c)
    async def run():
        await r.emit('grid_loss_2', '2 losses', severity='warning', notify=True)
        await r.emit('grid_loss_2', '2 losses', severity='warning', notify=True)
    asyncio.run(run())
    assert len(c.hass.bus.events) == 2
    assert len(c.hass.services.calls) == 1


def test_no_telegram_without_configured_notify_entity():
    c = Controller(notify=None)
    r = reporter.EventReporter(c)
    asyncio.run(r.emit('write_failed', 'write failed', severity='error', notify=True))
    assert len(c.hass.bus.events) == 1
    assert c.hass.services.calls == []
