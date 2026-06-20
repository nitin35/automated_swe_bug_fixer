import asyncio
import pytest
import time
from src.bus import MessageBus
from src.models import Directive, Event
from src.agents.base import BaseAgent

class DummyAgent(BaseAgent):
    async def execute(self, directive: Directive) -> dict:
        if directive.action == "fail":
            raise ValueError("Simulated failure")
        return {"status": "success", "echo": directive.payload.get("data")}

@pytest.mark.anyio
async def test_message_bus_routing():
    bus = MessageBus()
    
    # Create master and agent queues
    bus.register_agent("master", None)
    bus.register_agent("test_agent", None)
    
    directive = Directive(
        target="test_agent",
        action="echo",
        message_id="msg_123",
        payload={"data": "hello"},
        run_id="run_1"
    )
    
    await bus.send_directive(directive)
    
    # Retrieve directive from agent queue
    retrieved = await bus.listen_for("test_agent", timeout=1, event_type="directive")
    assert retrieved == directive
    assert retrieved.message_id == "msg_123"

@pytest.mark.anyio
async def test_message_bus_subscribe():
    bus = MessageBus()
    received_events = []
    
    async def event_callback(event: Event):
        received_events.append(event)
        
    bus.subscribe("task.started", event_callback)
    
    event = Event(
        source="test_agent",
        type="task.started",
        message_id="msg_123",
        payload={"action": "echo"},
        timestamp=time.time(),
        run_id="run_1"
    )
    
    await bus.publish_event(event)
    assert len(received_events) == 1
    assert received_events[0].message_id == "msg_123"

@pytest.mark.anyio
async def test_message_bus_listen_filtering_and_requeue():
    bus = MessageBus()
    bus.register_agent("test_agent", None)
    
    # Queue multiple messages
    # 1. Non-matching directive
    directive = Directive(target="test_agent", action="do_x", message_id="d1")
    await bus._queues["test_agent"].put(("directive", directive))
    
    # 2. Matching event type
    event = Event(source="master", type="test_event", message_id="e1")
    await bus._queues["test_agent"].put(("event", event))
    
    # Listen for event
    retrieved_event = await bus.listen_for("test_agent", timeout=1, event_type="event")
    assert retrieved_event == event
    
    # Check that the non-matching directive is still in the queue (re-queued)
    retrieved_directive = await bus.listen_for("test_agent", timeout=1, event_type="directive")
    assert retrieved_directive == directive

@pytest.mark.anyio
async def test_base_agent_run_loop_success():
    bus = MessageBus()
    bus.register_agent("master", None)
    
    agent = DummyAgent(name="dummy", bus=bus)
    
    # Start agent loop as background task
    agent_task = asyncio.create_task(agent.run_loop())
    
    # Send success directive
    directive = Directive(
        target="dummy",
        action="echo",
        message_id="msg_success",
        payload={"data": "hello"},
        run_id="run_1"
    )
    await bus.send_directive(directive)
    
    # Retrieve started event from master queue
    started_event = await bus.listen_for("master", timeout=1, event_type="event")
    assert started_event.type == "task.started"
    assert started_event.message_id == "msg_success"
    
    # Retrieve completed event from master queue
    completed_event = await bus.listen_for("master", timeout=1, event_type="event")
    assert completed_event.type == "task.completed"
    assert completed_event.message_id == "msg_success"
    assert completed_event.payload == {"status": "success", "echo": "hello"}
    
    agent_task.cancel()

@pytest.mark.anyio
async def test_base_agent_run_loop_failure():
    bus = MessageBus()
    bus.register_agent("master", None)
    
    agent = DummyAgent(name="dummy", bus=bus)
    
    # Start agent loop as background task
    agent_task = asyncio.create_task(agent.run_loop())
    
    # Send fail directive
    directive = Directive(
        target="dummy",
        action="fail",
        message_id="msg_fail",
        payload={},
        run_id="run_1"
    )
    await bus.send_directive(directive)
    
    # Retrieve started event from master queue
    started_event = await bus.listen_for("master", timeout=1, event_type="event")
    assert started_event.type == "task.started"
    
    # Retrieve failed event from master queue
    failed_event = await bus.listen_for("master", timeout=1, event_type="event")
    assert failed_event.type == "task.failed"
    assert "error" in failed_event.payload
    assert "Simulated failure" in failed_event.payload["error"]

    
    agent_task.cancel()
