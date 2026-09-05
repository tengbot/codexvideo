import json
from types import SimpleNamespace

import pytest

from codexvideo.execution import invoke_tool
from tools.base_tool import ToolResult, ToolRuntime, ToolStatus
from tools.cost_tracker import BudgetExceededError


@pytest.fixture
def run(tmp_path, monkeypatch):
    (tmp_path / "project.json").write_text(json.dumps({"project_id": tmp_path.name, "pipeline_type": "framework-smoke"}))
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/consumer_request.json").write_text('{"execution":{"budget_usd":1}}')
    calls = []
    tool = SimpleNamespace(name="unit", version="1", provider="unit", capability="unit",
                           runtime=ToolRuntime.API, input_schema={"type": "object"},
                           estimate_cost=lambda inputs: 0.5, get_status=lambda: ToolStatus.AVAILABLE,
                           execute=lambda inputs: calls.append(inputs) or ToolResult(success=True, cost_usd=0.5))
    monkeypatch.setattr("codexvideo.execution.registry.ensure_discovered", lambda: None)
    monkeypatch.setattr("codexvideo.execution.registry.get", lambda name: tool)
    monkeypatch.setattr("codexvideo.execution.load_pipeline_readonly", lambda _: {"stages": [{"name": "research", "tools_available": ["unit"]}]})
    return tmp_path, tool, calls


def _approve(project, plan):
    path = project / "approval.json"
    path.write_text(json.dumps({**plan["approval_template"], "approved": True, "user_statement": "Explicit test fixture approval"}))
    return path


def test_prepare_never_executes_and_paid_call_requires_approval(run):
    project, tool, calls = run
    plan = invoke_tool(project, "research", "unit", {}, "one")
    assert not plan["executed"] and not calls
    with pytest.raises(ValueError, match="approval"):
        invoke_tool(project, "research", "unit", {}, "one", True)
    assert not calls


def test_per_call_approval_binding_budget_and_duplicate_protection(run):
    project, tool, calls = run
    plan = invoke_tool(project, "research", "unit", {}, "one")
    approval = _approve(project, plan)
    with pytest.raises(ValueError, match="match"):
        invoke_tool(project, "research", "unit", {"text": "changed"}, "one", True, approval)
    assert not calls
    result = invoke_tool(project, "research", "unit", {}, "one", True, approval)
    assert result["status"] == "completed" and len(calls) == 1
    with pytest.raises(ValueError, match="already dispatched"):
        invoke_tool(project, "research", "unit", {}, "one", True, approval)
    tool.estimate_cost = lambda _: 0.75
    approval = _approve(project, invoke_tool(project, "research", "unit", {}, "two"))
    with pytest.raises(BudgetExceededError):
        invoke_tool(project, "research", "unit", {}, "two", True, approval)
    assert len(calls) == 1
    assert not (project / ".execution-lock").exists()


def test_uncertain_paid_failure_preserves_reservation(run):
    project, tool, calls = run
    def fail(_):
        raise TimeoutError("provider response lost")
    tool.execute = fail
    approval = _approve(project, invoke_tool(project, "research", "unit", {}, "one"))
    result = invoke_tool(project, "research", "unit", {}, "one", True, approval)
    assert result["status"] == "uncertain" and result["reconciliation_pending"]
    assert json.loads((project / "cost_log.json").read_text())["budget_reserved_usd"] == 0.5


def test_local_tool_needs_no_paid_approval_and_changed_file_invalidates_it(run):
    project, tool, calls = run
    source = project / "script.json"
    source.write_text('{"text":"first"}')
    inputs = {"script_path": str(source)}
    approval = _approve(project, invoke_tool(project, "research", "unit", inputs, "one"))
    source.write_text('{"text":"changed"}')
    with pytest.raises(ValueError, match="match"):
        invoke_tool(project, "research", "unit", inputs, "one", True, approval)
    tool.runtime = ToolRuntime.LOCAL
    tool.estimate_cost = lambda _: 0
    tool.execute = lambda _: ToolResult(success=True)
    assert invoke_tool(project, "research", "unit", inputs, "one", True)["status"] == "completed"
