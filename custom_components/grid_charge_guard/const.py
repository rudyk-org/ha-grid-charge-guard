"""Constants for Grid Charge Guard."""

DOMAIN = "grid_charge_guard"
CONF_NOTIFY_ENTITY = "notify_entity"
EVENT_NAME = "grid_charge_guard_event"
NOTIFY_COOLDOWN_SECONDS = 15 * 60
WRITE_CONFIRM_TIMEOUT_SECONDS = 65
CONF_VOLTAGE_ENTITY = "voltage_entity"
CONF_CURRENT_ENTITY = "current_entity"
DEFAULT_MAX = 60
MIN_CURRENT = 5
MAX_CURRENT = 100
OUTAGE_VOLTAGE = 50.0
RECOVERY_VOLTAGE = 180.0
OUTAGE_WINDOW = 15 * 60
DERATE_HOLD = 30 * 60
STABLE_RAMP_SECONDS = 5 * 60
RAMP_STEP = 5
VOLTAGE_AVERAGE_WINDOW_SECONDS = 180
VOLTAGE_AVERAGE_WARMUP_SECONDS = 120
VOLTAGE_AVERAGE_MIN_SAMPLES = 8
POLL_SECONDS = 10
STORAGE_VERSION = 1

# Live-editable tuning parameters, exposed as native HA number entities.
# Hardware voltage cutoffs and grid-loss safety tiers remain fixed.
SETTING_SPECS = {
    "min_current": dict(name="Minimum AC charge current", minimum=5, maximum=50, step=5, default=10, unit="A", icon="mdi:current-dc"),
    "ramp_up_step": dict(name="Charge ramp up step", minimum=5, maximum=20, step=5, default=5, unit="A", icon="mdi:trending-up"),
    "moderate_drop_step": dict(name="Moderate voltage drop step", minimum=5, maximum=20, step=5, default=5, unit="A", icon="mdi:trending-down"),
    "severe_drop_step": dict(name="Severe voltage drop step", minimum=5, maximum=30, step=5, default=10, unit="A", icon="mdi:arrow-down-bold"),
    "ramp_interval_minutes": dict(name="Charge ramp interval", minimum=2, maximum=15, step=1, default=3, unit="min", icon="mdi:timer-plus"),
    "moderate_drop_interval_seconds": dict(name="Moderate drop interval", minimum=30, maximum=300, step=30, default=120, unit="s", icon="mdi:timer-minus"),
    "severe_drop_interval_seconds": dict(name="Severe drop interval", minimum=30, maximum=180, step=15, default=45, unit="s", icon="mdi:timer-alert"),
    "average_window_minutes": dict(name="Voltage averaging window", minimum=2, maximum=10, step=1, default=3, unit="min", icon="mdi:chart-bell-curve"),
}
