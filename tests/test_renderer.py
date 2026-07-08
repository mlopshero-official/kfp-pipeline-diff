from kfp_pipeline_diff.parser import TaskNode
from kfp_pipeline_diff.diff import diff_pipelines
from kfp_pipeline_diff.renderer import generate_mermaid_chart, generate_markdown_report


def test_generate_mermaid_chart():
    # Before tasks
    task_a_before = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_before = TaskNode("task-b", "comp-b", ["task-a"], "python:3.9")
    before = {"task-a": task_a_before, "task-b": task_b_before}

    # After tasks
    task_a_after = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_after = TaskNode("task-b", "comp-b", ["task-a"], "python:3.11")  # modified
    task_c_after = TaskNode("task-c", "comp-c", ["task-b"], "python:3.11")  # added
    after = {"task-a": task_a_after, "task-b": task_b_after, "task-c": task_c_after}

    diff = diff_pipelines(before, after)
    chart = generate_mermaid_chart(diff)

    # Verify formatting keywords exist
    assert "flowchart TD" in chart
    assert "classDef added" in chart
    assert "classDef removed" in chart
    assert "classDef modified" in chart
    assert "classDef unchanged" in chart

    # Check node classes application
    assert "class" in chart
    assert "added" in chart
    assert "modified" in chart
    assert "unchanged" in chart

    # Check edge rendering
    assert "-->" in chart


def test_generate_markdown_report():
    # Before tasks
    task_a_before = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_before = TaskNode("task-b", "comp-b", ["task-a"], "python:3.9")
    before = {"task-a": task_a_before, "task-b": task_b_before}

    # After tasks
    task_a_after = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_after = TaskNode("task-b", "comp-b", ["task-a"], "python:3.11")  # modified
    task_c_after = TaskNode("task-c", "comp-c", ["task-b"], "python:3.11")  # added
    after = {"task-a": task_a_after, "task-b": task_b_after, "task-c": task_c_after}

    diff = diff_pipelines(before, after)
    report = generate_markdown_report(diff, pr_number=42)

    assert "## 🧬 KFP DAG Structure Diff" in report
    assert "PR #42" in report
    assert "Summary Statistics" in report
    assert "Unified DAG Diagram" in report
    assert "Detailed Task Property Changes" in report
    assert "task-b" in report
