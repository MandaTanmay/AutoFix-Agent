from typing import Optional
from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import AgentNodeHandler
from app.agent.routing import (
    check_runtime_error,
    check_validation_passed,
    check_retry_decision,
)


def create_autofix_graph(handler: Optional[AgentNodeHandler] = None):
    """
    Builds the test-driven AutoFix Agent LangGraph StateGraph.

    Graph Architecture:
    START
      ↓
    EXECUTE
      ↓
    OBSERVE
      ↓
    check_runtime_error
      ├── runtime_error (crash / exception) → DIAGNOSE
      └── validate (clean execution)
           ↓
        VALIDATE (initial test run)
           ↓
        check_validation_passed
           ├── success (tests pass) → END
           └── needs_repair (tests fail / logic bug)
                ↓
             DIAGNOSE
                ↓
              PATCH
                ↓
             VALIDATE (validate repaired patch)
                ↓
              RETRY (record history snapshot)
                ↓
             check_retry_decision
                ├── success → END
                ├── max_attempts_reached → END
                └── retry → EXECUTE
    """
    node_handler = handler or AgentNodeHandler()

    workflow = StateGraph(AgentState)

    # Register workflow nodes
    workflow.add_node("execute", node_handler.execute_node)
    workflow.add_node("observe", node_handler.observe_node)
    workflow.add_node("validate_initial", node_handler.validate_node)
    workflow.add_node("diagnose", node_handler.diagnose_node)
    workflow.add_node("patch", node_handler.patch_node)
    workflow.add_node("validate_repaired", node_handler.validate_node)
    workflow.add_node("retry", node_handler.retry_node)

    # Initial flow
    workflow.add_edge(START, "execute")
    workflow.add_edge("execute", "observe")

    # Step 1: Check runtime execution
    workflow.add_conditional_edges(
        "observe",
        check_runtime_error,
        {
            "runtime_error": "diagnose",
            "validate": "validate_initial",
        },
    )

    # Step 2: Check initial validation (detects logic bugs when execution doesn't crash)
    workflow.add_conditional_edges(
        "validate_initial",
        check_validation_passed,
        {
            "success": END,
            "needs_repair": "diagnose",
        },
    )

    # Step 3: Repair loop
    workflow.add_edge("diagnose", "patch")
    workflow.add_edge("patch", "validate_repaired")
    workflow.add_edge("validate_repaired", "retry")

    # Step 4: Decision to terminate or retry
    workflow.add_conditional_edges(
        "retry",
        check_retry_decision,
        {
            "success": END,
            "max_attempts_reached": END,
            "retry": "execute",
        },
    )

    return workflow.compile()
