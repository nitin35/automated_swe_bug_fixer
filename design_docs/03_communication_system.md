# 03 — Communication System (Message Bus)

## 3.1 Design Principles

- **Minimal:** The bus does one thing — route messages between agents
- **In-process:** No network overhead for MVP; all agents live in the same process
- **Async-native:** Built on `asyncio` primitives
- **Typed:** Messages have a well-defined schema (see [data models](07_data_models.md))
- **Observable:** All messages are logged for debugging and replay

## 3.2 Architecture

```
                    ┌──────────────────────┐
                    │    Message Bus       │
                    │ (Event Loop + Queues)│
                    └──┬──┬──┬──┬──┬──┬──┬─┘
                       │  │  │  │  │  │  │
                    Agent1 Agent2 ... AgentN
                          Master Agent
```

The bus is central: every agent (including the Master) communicates **only through the bus**.

## 3.3 Message Types

### Directives (Master → Agent)
Commands from the Master telling an agent to do something.

```python
@dataclass
class Directive:
    target: str           # Agent name
    action: str           # Action identifier (e.g., "reproduce_bug", "generate_fix")
    message_id: str       # Unique ID for tracking
    payload: dict         # Action-specific data
    priority: int = 0     # Higher = more urgent
    timeout: int = 300    # Max execution time in seconds
```

### Events (Agent → Bus → Anyone)
Notifications from agents about what happened.

```python
@dataclass
class Event:
    source: str           # Agent name that emitted the event
    type: str             # Event type (see 3.4)
    message_id: str       # Correlates to the Directive (if applicable)
    payload: dict         # Event-specific data
    timestamp: float      # When the event was created
```


## 3.4 Event Types

| Event Type | Emitter | Meaning |
|------------|---------|---------|
| `task.started` | Any agent | Agent began working on a directive |
| `task.progress` | Any agent | Intermediate update (e.g., "cloning repo...") |
| `task.completed` | Any agent | Task finished successfully |
| `task.failed` | Any agent | Task finished with error |
| `task.timeout` | Bus (automatic) | Agent did not respond in time |
| `log.message` | Any agent | A log entry for the knowledge base |
| `knowledge.updated` | Any agent | Agent added something to the KB |
| `hitl.review_needed` | Master | Validation passed, waiting for human approval |
| `hitl.decision` | Human/UI | Human approved or rejected the fix |
| `system.shutdown` | Master | Graceful shutdown signal |

## 3.5 Bus Implementation (MVP)

```python
import asyncio

class MessageBus:
    def __init__(self):
        self._agents = {}                      # name -> Agent handle
        self._queues: dict[str, asyncio.Queue] = {}  # Regular dict, not defaultdict
        self._listeners: dict[str, list] = {}  # event_type -> [callbacks]
        self._history: list[Event] = []         # Full message log

    def register_agent(self, name, agent):
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

    async def listen_for(self, agent_name, timeout=None, event_type=None):
        """Listen for incoming messages. Non-matching messages are re-queued."""
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

    def subscribe(self, event_type, callback):
        """Subscribe a callback to an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def get_history(self, filter_type=None):
        """Return event history, optionally filtered."""
        if filter_type:
            return [e for e in self._history if e.type == filter_type]
        return self._history
```

## 3.6 Agent Communication Pattern

Each agent runs an async loop:

```python
class BaseAgent(ABC):
    """Base class for all sub-agents (NOT the Master)."""

    def __init__(self, name: str, bus: MessageBus, llm: LLMRouter, kb: KnowledgeBase):
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
                source=self.name, type="task.started",
                message_id=directive.message_id,
                payload={"action": directive.action},
                timestamp=time.time(),
            ))
            try:
                result = await self.execute(directive)
                await self.bus.publish_event(Event(
                    source=self.name, type="task.completed",
                    message_id=directive.message_id,
                    payload=result,
                    timestamp=time.time(),
                ))
            except Exception as e:
                await self.bus.publish_event(Event(
                    source=self.name, type="task.failed",
                    message_id=directive.message_id,
                    payload={"error": str(e)},
                    timestamp=time.time(),
                ))
```

## 3.7 Message Flow Example (MVP Bug Fix)

```
Master                      Bus                 Reproduction Agent
  │                          │                          │
  │── send_directive ────────│─── directive ───────────>│
  │  (target=reproduction)   │                          │
  │                          │                          │ execute reproduce_bug()
  │<── publish_event ────────│<── task.started ─────────│
  │                          │                          │
  │                          │                          │ ...cloning repo...
  │<── publish_event ────────│<── task.progress ────────│
  │                          │                          │
  │                          │                          │ ...done!
  │<── publish_event ────────│<── task.completed ───────│
  │  (type=task.completed)   │     (payload={...})      │
  │                          │                          │
  │── send_directive ────────│─── directive ───────────>│ Fix Agent
  │  (target=fix)            │                          │
  │                          │                          │ ...
```

## 3.8 Future Enhancements (Not for MVP)

- **Message persistence**: Save all messages to SQLite for replay/debugging
- **Distributed bus**: Replace in-process queues with Redis/NATS
- **Priority queues**: Urgent messages skip the line
- **Dead letter queue**: Failed messages stored for analysis
- **Query messages**: Request/response pattern for inter-agent queries (designed but deferred)