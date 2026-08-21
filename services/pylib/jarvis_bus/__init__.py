"""jarvis_bus — shared Python library for jv-* services.

Contents: generated schema bindings (see tools/gen_bindings.py) and the
asyncio bus client speaking jarvisd's wire protocol.
"""

from . import schema  # noqa: F401
from .client import BusClient, BusError, default_addr, mono_now  # noqa: F401
