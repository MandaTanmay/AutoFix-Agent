from typing import Literal
from app.agent.state import AgentState


def check_initial_execution(state: AgentState) -> Literal["success", "needs_repair"]:
    """
    Evaluates the result of the observation phase.
    If the code executed successfully, terminate to END.
    Otherwise, proceed to diagnosis and patching.
    """
    exec_result = state.get("execution_result")
    if exec_result and exec_result.success:
        return "success"
    return "needs_repair"


def check_validation_decision(state: AgentState) -> Literal["success", "retry", "max_attempts_reached"]:
    """
    Evaluates the result after validate_node.
    If validation passed, terminate successfully.
    If attempts reached max_attempts, terminate with limit reached.
    Otherwise, route to retry / re-execution.
    """
    val_result = state.get("validation_result")
    if val_result and val_result.success:
        return "success"

    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 5)

    if attempt >= max_attempts:
        return "max_attempts_reached"

    return "retry"
