from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Intent:
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class Callbacks:
    """Event callbacks for VoiceAssistant.

    All callbacks are invoked synchronously on the loop thread.
    They must be fast — a slow callback stalls the next listen cycle.
    Callbacks that raise are caught and logged; the loop continues.
    """
    on_transcript: Optional[Callable[[str], None]] = None
    on_intent: Optional[Callable[["Intent", str], None]] = None  # (intent, raw_text)
    on_status: Optional[Callable[[str, Optional[str]], None]] = None  # (status, detail)
    on_error: Optional[Callable[[Exception, str], None]] = None  # (exception, context)
