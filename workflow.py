"""LangGraph workflow.

Wires the seven agents into a state machine:

    planner -> retriever -> validator -> [gate]
                              gate fails -> report (with errors)
                              gate passes -> ratios -> comparator -> analyst
                              -> critic -> [loop back to analyst if rejected]
                              -> report

The graph is the central nervous system of the workflow. Conditional edges
let the critic send work back to the analyst for revision.
"""
from langgraph.graph import StateGraph, END
from state import AnalysisState

from agents.planner import planner_agent
from agents.retriever import retriever_agent
from agents.validator import validator_agent
from agents.ratio_calculator import ratio_agent
from agents.comparator import comparator_agent
from agents.analyst import analyst_agent
from agents.critic import critic_agent
from agents.report_writer import report_writer_agent


# --- Conditional edge functions ---

def after_planner(state: AnalysisState) -> str:
    """If the planner errored (e.g., no tickers found), jump straight to report."""
    if state.get("error"):
        return "report"
    return "retriever"


def after_retriever(state: AnalysisState) -> str:
    if state.get("error") and not state.get("raw_data"):
        return "report"
    return "validator"


def after_validator(state: AnalysisState) -> str:
    """Skip downstream analysis if no ticker passed quality checks."""
    if not state.get("validation_passed"):
        return "report"
    return "ratios"


def after_critic(state: AnalysisState) -> str:
    """The heart of the self-critique loop.

    If the critic rejected the draft AND we haven't hit max rounds yet,
    send back to the analyst for revision. Otherwise, ship the report.
    """
    if state.get("insights_approved"):
        return "report"
    return "analyst"  # revise


def build_workflow():
    """Construct and compile the LangGraph workflow."""
    g = StateGraph(AnalysisState)

    # Register nodes
    g.add_node("planner", planner_agent)
    g.add_node("retriever", retriever_agent)
    g.add_node("validator", validator_agent)
    g.add_node("ratios", ratio_agent)
    g.add_node("comparator", comparator_agent)
    g.add_node("analyst", analyst_agent)
    g.add_node("critic", critic_agent)
    g.add_node("report", report_writer_agent)

    # Entry point
    g.set_entry_point("planner")

    # Conditional routing
    g.add_conditional_edges("planner", after_planner,
                            {"retriever": "retriever", "report": "report"})
    g.add_conditional_edges("retriever", after_retriever,
                            {"validator": "validator", "report": "report"})
    g.add_conditional_edges("validator", after_validator,
                            {"ratios": "ratios", "report": "report"})

    # Linear stretch
    g.add_edge("ratios", "comparator")
    g.add_edge("comparator", "analyst")
    g.add_edge("analyst", "critic")

    # Critic loop
    g.add_conditional_edges("critic", after_critic,
                            {"analyst": "analyst", "report": "report"})

    # Report is the terminal node
    g.add_edge("report", END)

    return g.compile()


# Module-level compiled graph - import once, reuse
WORKFLOW = build_workflow()


def run_analysis(user_query: str) -> AnalysisState:
    """Convenience entry point: run the full workflow on a query."""
    initial_state: AnalysisState = {
        "user_query": user_query,
        "log": [],
        "critic_round": 0,
    }
    final_state = WORKFLOW.invoke(initial_state)
    return final_state
