from langgraph.graph import StateGraph, START, END
from app.models.state import HealingState
from app.agents.nodes.repo_analyzer import repo_analyzer_node
from app.agents.nodes.test_runner import test_runner_node
from app.agents.nodes.bug_classifier import bug_classifier_node
from app.agents.nodes.fix_generator import fix_generator_node
from app.agents.nodes.fix_validator import fix_validator_node
from app.agents.nodes.git_ops import git_ops_node
from app.agents.nodes.ci_monitor import ci_monitor_node
from app.agents.nodes.scorer import scorer_node


def route_after_tests(state: HealingState) -> str:
    if state.get("all_tests_passing", False):
        return "scorer"
    return "bug_classifier"


def route_after_ci(state: HealingState) -> str:
    if state.get("ci_passed", False) or state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "scorer"
    return "test_runner"


def build_graph():
    g = StateGraph(HealingState)

    g.add_node("repo_analyzer", repo_analyzer_node)
    g.add_node("test_runner", test_runner_node)
    g.add_node("bug_classifier", bug_classifier_node)
    g.add_node("fix_generator", fix_generator_node)
    g.add_node("fix_validator", fix_validator_node)
    g.add_node("git_ops", git_ops_node)
    g.add_node("ci_monitor", ci_monitor_node)
    g.add_node("scorer", scorer_node)

    g.add_edge(START, "repo_analyzer")
    g.add_edge("repo_analyzer", "test_runner")
    g.add_conditional_edges(
        "test_runner",
        route_after_tests,
        {"scorer": "scorer", "bug_classifier": "bug_classifier"},
    )
    g.add_edge("bug_classifier", "fix_generator")
    g.add_edge("fix_generator", "fix_validator")
    g.add_edge("fix_validator", "git_ops")
    g.add_edge("git_ops", "ci_monitor")
    g.add_conditional_edges(
        "ci_monitor",
        route_after_ci,
        {"scorer": "scorer", "test_runner": "test_runner"},
    )
    g.add_edge("scorer", END)

    return g.compile()
