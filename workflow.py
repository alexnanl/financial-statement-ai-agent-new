"""LangGraph workflow v2.

Order:
  planner -> retriever -> [gate] -> validator -> [gate]
  -> ratios -> trend_analyzer -> comparator -> peer_selector
  -> peer_retriever -> peer_analyzer -> chart_builder
  -> analyst -> critic -> [loop or report]
  -> report_writer
"""
from langgraph.graph import StateGraph, END
from state import AnalysisState

from agents.planner import planner_agent
from agents.retriever import retriever_agent, peer_retriever_agent
from agents.validator import validator_agent
from agents.ratio_calculator import ratio_agent
from agents.trend_analyzer import trend_analyzer_agent
from agents.comparator import comparator_agent
from agents.peer_selector import peer_selector_agent
from agents.peer_analyzer import peer_analyzer_agent
from agents.fundamentals import fundamentals_agent
from agents.flags import flags_agent
from agents.chart_builder import chart_builder_agent
from agents.analyst import analyst_agent
from agents.critic import critic_agent
from agents.report_writer import report_writer_agent


def after_planner(state):
    return "report" if state.get("error") else "retriever"


def after_retriever(state):
    if state.get("error") and not state.get("raw_data"):
        return "report"
    return "validator"


def after_validator(state):
    return "ratios" if state.get("validation_passed") else "report"


def after_critic(state):
    """If rejected and we haven't hit max rounds, loop back to Analyst."""
    return "report" if state.get("insights_approved") else "analyst"


def build_workflow():
    g = StateGraph(AnalysisState)

    g.add_node("planner", planner_agent)
    g.add_node("retriever", retriever_agent)
    g.add_node("validator", validator_agent)
    g.add_node("ratios", ratio_agent)
    g.add_node("trend_analyzer", trend_analyzer_agent)
    g.add_node("comparator", comparator_agent)
    g.add_node("peer_selector", peer_selector_agent)
    g.add_node("peer_retriever", peer_retriever_agent)
    g.add_node("peer_analyzer", peer_analyzer_agent)
    g.add_node("fundamentals", fundamentals_agent)
    g.add_node("flags", flags_agent)
    g.add_node("chart_builder", chart_builder_agent)
    g.add_node("analyst", analyst_agent)
    g.add_node("critic", critic_agent)
    g.add_node("report", report_writer_agent)

    g.set_entry_point("planner")

    g.add_conditional_edges("planner", after_planner,
                            {"retriever": "retriever", "report": "report"})
    g.add_conditional_edges("retriever", after_retriever,
                            {"validator": "validator", "report": "report"})
    g.add_conditional_edges("validator", after_validator,
                            {"ratios": "ratios", "report": "report"})

    # Linear analytical pipeline
    g.add_edge("ratios", "trend_analyzer")
    g.add_edge("trend_analyzer", "comparator")
    g.add_edge("comparator", "peer_selector")
    g.add_edge("peer_selector", "peer_retriever")
    g.add_edge("peer_retriever", "peer_analyzer")
    g.add_edge("peer_analyzer", "fundamentals")
    g.add_edge("fundamentals", "flags")
    g.add_edge("flags", "chart_builder")
    g.add_edge("chart_builder", "analyst")
    g.add_edge("analyst", "critic")

    g.add_conditional_edges("critic", after_critic,
                            {"analyst": "analyst", "report": "report"})

    g.add_edge("report", END)
    return g.compile()


WORKFLOW = build_workflow()


def run_analysis(user_query: str) -> AnalysisState:
    initial_state: AnalysisState = {
        "user_query": user_query,
        "log": [],
        "critic_round": 0,
    }
    return WORKFLOW.invoke(initial_state)
