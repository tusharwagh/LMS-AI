import pytest

from lms.agent.graph import compile_issue_sop_graph

pytestmark = pytest.mark.unit


def test_issue_sop_graph_compiles_and_runs() -> None:
    graph = compile_issue_sop_graph()
    result = graph.invoke({"step": "start"}, config={"configurable": {"thread_id": "test-thread"}})
    assert result.get("step") == "respond"
