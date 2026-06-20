import asyncio
from src.models import Directive, Event

class MessageBus:
    def __init__(self):
        self._agents = {}                      # name -> Agent handle
        self._queues: dict[str, asyncio.Queue] = {}  # Regular dict, not defaultdict
        self._listeners: dict[str, list] = {}  # event_type -> [callbacks]
        self._history: list[Event] = []         # Full message log

    def register_agent(self, name: str, agent):
        """Register an agent so the bus can route to it."""
        self._agents[name] = agent
        self._queues[name] = asyncio.Queue()

    async def send_directive(self, directive: Directive):
        """Send a directive to a specific agent."""
        if directive.target not in self._agents:
            raise ValueError(f"Unknown agent: {directive.target}")
        await self._queues[directive.target].put(("directive", directive))

    async def publish_event(self, event: Event):
        """Broadcast an event to all subscribers."""
        self._history.append(event)
        # Notify direct listeners
        for callback in self._listeners.get(event.type, []):
            await callback(event)
        # Notify the master (always listens), but filter out its own events
        if "master" in self._agents and event.source != "master":
            await self._queues["master"].put(("event", event))

    async def listen_for(self, agent_name: str, timeout=None, event_type=None):
        """Listen for incoming messages. Non-matching messages are re-queued."""
        if agent_name not in self._queues:
            raise ValueError(f"Agent '{agent_name}' is not registered with the bus")
        queue = self._queues[agent_name]
        skipped = []
        try:
            while True:
                msg_type, msg = await asyncio.wait_for(queue.get(), timeout=timeout)
                if event_type and msg_type != event_type:
                    skipped.append((msg_type, msg))  # Save, don't drop
                    continue
                return msg
        except asyncio.TimeoutError:
            raise TimeoutError(f"Agent '{agent_name}' timed out waiting for message")
        finally:
            # Re-queue any skipped messages so they aren't lost
            for item in skipped:
                await queue.put(item)

    def subscribe(self, event_type: str, callback):
        """Subscribe a callback to an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def get_history(self, filter_type=None) -> list[Event]:
        """Return event history, optionally filtered."""
        if filter_type:
            return [e for e in self._history if e.type == filter_type]
        return self._history
