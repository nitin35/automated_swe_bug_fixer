import time
from abc import ABC, abstractmethod
from src.bus import MessageBus
from src.models import Directive, Event

class BaseAgent(ABC):
    """Base class for all sub-agents (NOT the Master)."""

    def __init__(self, name: str, bus: MessageBus, llm=None, kb=None):
        self.name = name
        self.bus = bus
        self.llm = llm
        self.kb = kb
        bus.register_agent(name, self)

    @abstractmethod
    async def execute(self, directive: Directive) -> dict:
        """Execute a directive and return a result dict."""
        pass

    async def run_loop(self):
        """Main loop: listen for directives, execute, publish results."""
        while True:
            directive = await self.bus.listen_for(self.name, event_type="directive")

            await self.bus.publish_event(Event(
                source=self.name,
                type="task.started",
                message_id=directive.message_id,
                payload={"action": directive.action},
                timestamp=time.time(),
                run_id=directive.run_id
            ))
            try:
                result = await self.execute(directive)
                await self.bus.publish_event(Event(
                    source=self.name,
                    type="task.completed",
                    message_id=directive.message_id,
                    payload=result,
                    timestamp=time.time(),
                    run_id=directive.run_id
                ))
            except Exception as e:
                await self.bus.publish_event(Event(
                    source=self.name,
                    type="task.failed",
                    message_id=directive.message_id,
                    payload={"error": str(e)},
                    timestamp=time.time(),
                    run_id=directive.run_id
                ))
