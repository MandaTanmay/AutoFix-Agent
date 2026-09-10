import os
import uuid
import asyncio
from typing import AsyncGenerator, List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    RepairRequest,
    RepairResponse,
    HealthResponse,
    AgentEvent,
)
from app.streaming.events import SSEEvent, SSEEventType
from app.streaming.emitter import node_to_sse_events
from app.execution.manager import ExecutionManager
from app.validation.manager import ValidationManager
from app.analysis.error_parser import ErrorParser
from app.llm.client import LLMDiagnosisClient
from app.agent.graph import create_autofix_graph
from app.agent.nodes import AgentNodeHandler
from app.agent.state import AgentState

# Load environment variables
load_dotenv()

app = FastAPI(
    title="AutoFix Agent API",
    version="0.2.0",
    description="Backend API service for autonomous code repair agent",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        service="autofix-agent",
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_code(request: AnalyzeRequest):
    """
    Executes code and observes/parses errors without initiating repairs.
    """
    try:
        exec_manager = ExecutionManager(default_timeout=request.timeout or 5.0)
        exec_result = exec_manager.execute(language=request.language, code=request.source_code)

        error_observation = None
        if not exec_result.success:
            error_observation = ErrorParser.parse(exec_result)

        return AnalyzeResponse(
            language=request.language.lower(),
            execution_result=exec_result,
            error_observation=error_observation,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while analyzing code: {str(exc)}",
        )


@app.post("/api/repair", response_model=RepairResponse)
def repair_code(request: RepairRequest):
    """
    Runs the autonomous code repair LangGraph workflow.
    """
    if not request.source_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_code cannot be empty.",
        )

    session_id = str(uuid.uuid4())
    timeout = request.timeout or 5.0

    try:
        exec_manager = ExecutionManager(default_timeout=timeout)
        val_manager = ValidationManager(default_timeout=timeout + 3.0)
        diag_client = LLMDiagnosisClient()

        handler = AgentNodeHandler(
            execution_manager=exec_manager,
            validation_manager=val_manager,
            diagnosis_client=diag_client,
        )
        graph = create_autofix_graph(handler)

        initial_state: AgentState = {
            "original_code": request.source_code,
            "current_code": request.source_code,
            "test_code": request.test_code,
            "language": request.language.lower(),
            "attempt": 0,
            "max_attempts": request.max_attempts or 5,
            "execution_result": None,
            "error_observation": None,
            "diagnosis": None,
            "patch": None,
            "validation_result": None,
            "history": [],
            "status": "running",
        }

        # Execute the LangGraph workflow
        final_state = graph.invoke(initial_state)

        # Synthesize concise agent events from history and final state
        events: List[AgentEvent] = []
        events.append(
            AgentEvent(
                type="execution",
                attempt=0,
                message=f"Initial code execution completed ({'Passed' if final_state.get('execution_result') and final_state['execution_result'].success else 'Error detected'}).",
            )
        )

        for item in final_state.get("history", []):
            if item.diagnosis:
                events.append(
                    AgentEvent(
                        type="diagnosis",
                        attempt=item.attempt,
                        message=item.diagnosis,
                    )
                )
            if item.patch:
                events.append(
                    AgentEvent(
                        type="patch",
                        attempt=item.attempt,
                        message=f"Attempt #{item.attempt} patch synthesized.",
                    )
                )
            events.append(
                AgentEvent(
                    type="validation",
                    attempt=item.attempt,
                    message=f"Validation {item.validation_result}.",
                )
            )

        events.append(
            AgentEvent(
                type="completion",
                attempt=final_state.get("attempt", 0),
                message=f"Agent workflow finished with status: {final_state.get('status')}.",
            )
        )

        return RepairResponse(
            session_id=session_id,
            status=final_state.get("status", "failed"),
            language=request.language.lower(),
            attempts=final_state.get("attempt", 0),
            final_code=final_state.get("current_code", request.source_code),
            diagnosis=final_state.get("diagnosis"),
            validation_result=final_state.get("validation_result"),
            execution_result=final_state.get("execution_result"),
            history=final_state.get("history", []),
            events=events,
        )

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow encountered an error: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# SSE Streaming endpoint
# ---------------------------------------------------------------------------

async def _repair_event_generator(
    request: Request,
    repair_request: RepairRequest,
) -> AsyncGenerator[str, None]:
    """
    Async generator that runs the LangGraph repair workflow using .stream()
    and yields SSE-formatted event strings.

    The stream closes when:
    - Repair succeeds
    - Maximum attempts are reached
    - An unexpected error occurs
    - The client disconnects
    """
    session_id = str(uuid.uuid4())
    timeout = repair_request.timeout or 5.0

    # Emit session_started immediately
    yield SSEEvent.make(
        type=SSEEventType.SESSION_STARTED,
        message=f"AutoFix session started. Language: {repair_request.language.lower()}. Max attempts: {repair_request.max_attempts or 5}.",
        details={"session_id": session_id, "language": repair_request.language.lower()},
    ).to_sse_line()

    try:
        exec_manager = ExecutionManager(default_timeout=timeout)
        val_manager  = ValidationManager(default_timeout=timeout + 3.0)
        diag_client  = LLMDiagnosisClient()

        handler = AgentNodeHandler(
            execution_manager=exec_manager,
            validation_manager=val_manager,
            diagnosis_client=diag_client,
        )
        graph = create_autofix_graph(handler)

        initial_state: AgentState = {
            "original_code": repair_request.source_code,
            "current_code":  repair_request.source_code,
            "test_code":     repair_request.test_code,
            "language":      repair_request.language.lower(),
            "attempt":       0,
            "max_attempts":  repair_request.max_attempts or 5,
            "execution_result":  None,
            "error_observation": None,
            "diagnosis":         None,
            "patch":             None,
            "validation_result": None,
            "history":           [],
            "status":            "running",
        }

        # Track current attempt across node completions
        current_attempt = 0
        terminal_emitted = False

        # stream_mode="updates" yields {node_name: state_delta} dicts
        for chunk in graph.stream(initial_state, stream_mode="updates"):
            # Honour client disconnect
            if await request.is_disconnected():
                break

            for node_name, state_delta in chunk.items():
                # Update attempt from retry node
                if node_name == "retry" and "attempt" in state_delta:
                    current_attempt = state_delta["attempt"]

                sse_events = node_to_sse_events(
                    node_name=node_name,
                    state_delta=state_delta,
                    attempt=current_attempt,
                )

                for event in sse_events:
                    yield event.to_sse_line()
                    # Allow other coroutines to run (important for StreamingResponse)
                    await asyncio.sleep(0)

                    # If we emitted a terminal event, stop processing further chunks
                    if event.type in (SSEEventType.REPAIR_SUCCESS, SSEEventType.REPAIR_FAILED):
                        terminal_emitted = True

            if terminal_emitted:
                break

        # If we exited the loop without a terminal event (e.g. graph ended via END
        # without hitting the retry node), emit a fallback completion event.
        if not terminal_emitted:
            yield SSEEvent.make(
                type=SSEEventType.REPAIR_SUCCESS,
                message="Agent workflow completed.",
                attempt=current_attempt,
                status="success",
            ).to_sse_line()

    except ValueError as val_err:
        yield SSEEvent.make(
            type=SSEEventType.STREAM_ERROR,
            message=f"Invalid request: {val_err}",
            status="failed",
        ).to_sse_line()

    except Exception as exc:
        yield SSEEvent.make(
            type=SSEEventType.STREAM_ERROR,
            message=f"An unexpected error occurred: {exc}",
            status="failed",
        ).to_sse_line()


@app.post("/api/repair/stream")
async def repair_code_stream(request: Request, repair_request: RepairRequest):
    """
    Stream the autonomous code repair workflow as Server-Sent Events.

    Events are emitted in real-time as each LangGraph node completes.
    The stream closes when repair succeeds, fails, or max attempts are reached.
    """
    if not repair_request.source_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_code cannot be empty.",
        )

    return StreamingResponse(
        _repair_event_generator(request, repair_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering if behind proxy
            "Connection": "keep-alive",
        },
    )
