"""
Event Bus - Basit async pub/sub sistemi
"""

import asyncio
import traceback
from typing import Dict, Any, Callable, List

from app.utils.logger import get_logger

logger = get_logger("event_bus")


class EventBus:
    """
    Basit async event bus.
    Bileşenler arası gevşek bağlı iletişim sağlar.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Bir event tipine handler ekle."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed to '{event_type}': {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """Handler'ı kaldır."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def publish(self, event_type: str, data: Dict[str, Any] = None):
        """Event yayınla. Tüm subscriber'ları çağırır."""
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        data = data or {}
        data["_event_type"] = event_type

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(
                    f"Event handler error ({event_type}/{handler.__name__}): {e}\n"
                    f"{traceback.format_exc()}"
                )

    def get_subscriptions(self) -> Dict[str, int]:
        """Her event tipinin kaç handler'ı olduğunu döner."""
        return {k: len(v) for k, v in self._handlers.items()}
