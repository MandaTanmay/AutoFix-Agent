"""
Streaming layer for AutoFix Agent.

Translates LangGraph node execution events into Server-Sent Events (SSE)
suitable for real-time frontend consumption.
"""

from app.streaming.events import SSEEvent, SSEEventType
from app.streaming.emitter import node_to_sse_events

__all__ = ["SSEEvent", "SSEEventType", "node_to_sse_events"]
