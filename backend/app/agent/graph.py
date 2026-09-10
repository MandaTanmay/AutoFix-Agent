from typing import Optional
from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes import AgentNodeHandler
from app.agent.routing import check_initial_execution, check_validation_decision


def create_autofix_graph(handler: Optional[AgentNodeHandler] = None):
    """
    Builds and compiles the AutoFix Agent LangGraph StateGraph.

    Graph Architecture:
    START
      ↓
    EXECUTE
      ↓
    OBSERVE
      ↓
    SUCCESS?
      ├── YES → END
      └── NO
           ↓
        DIAGNOSE
           ↓
         PATCH
           ↓
        VALIDATE
           ↓
         RETRY (records history & checks limit)
           ↓
        DECISION?
         ├── YES (Passed) → END
         ├── MAX ATTEMPTS REACHED → END
         └── RETRY (Failed & under limit) → EXECUTE
    """
    node_handler = handler or AgentNodeHandler()

    workflow = StateGraph(AgentState)

    # Add processing nodes
    workflow.add_node("execute", node_handler.execute_node)
    workflow.add_node("observe", node_handler.observe_node)
    workflow.add_node("diagnose", node_handler.diagnose_node)
    workflow.add_node("patch", node_handler.patch_node)
    workflow.add_node("validate", node_handler.validate_node)
    workflow.add_node("retry", node_handler.retry_node)

    # Initial flow
    workflow.add_edge(START, "execute")
    workflow.add_edge("execute", "observe")

    # Conditional branch after observe
    workflow.add_conditional_edges(
        "observe",
        check_initial_execution,
        {
            "success": END,
            "needs_repair": "diagnose",
        },
    )

    # Repair pipeline
    workflow.add_edge("diagnose", "patch")
    workflow.add_edge("patch", "validate")
    workflow.add_edge("validate", "retry")

    # Conditional loop after retry
    workflow.add_conditional_edges(
        "retry",
        check_validation_decision,
        {
            "success": END,
            "max_attempts_reached": END,
            "retry": "execute",
        },
    )

    return workflow.compile()
