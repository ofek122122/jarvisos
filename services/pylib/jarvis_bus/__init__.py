"""jarvis_bus — shared Python library for jv-* services.

Contents: generated schema bindings (see tools/gen_bindings.py), the
asyncio bus client speaking jarvisd's wire protocol, and the heartbeat
clock every service's `sys.health` beat is owed against.
"""

from . import schema  # noqa: F401
from .client import BusClient, BusError, default_addr, mono_now  # noqa: F401
from .health import HealthBeat  # noqa: F401
