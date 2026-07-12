from kfp_pipeline_diff.parser import TaskNode
from kfp_pipeline_diff.diff import compare_task_properties, extract_edges, diff_pipelines


def test_compare_task_properties():
    node1 = TaskNode(
        name="task-a",
        component_ref="comp-1",
        dependent_tasks=[],
        image="python:3.9",
        command=["python"],
        args=["-c", "print(1)"],
        inputs={"parameters": {"x": 10}}
    )
    # Identical node
    node2 = TaskNode(
        name="task-a",
        component_ref="comp-1",
        dependent_tasks=[],
        image="python:3.9",
        command=["python"],
        args=["-c", "print(1)"],
        inputs={"parameters": {"x": 10}}
    )
    assert compare_task_properties(node1, node2) == {}

    # Modified image
    node3 = TaskNode(
        name="task-a",
        component_ref="comp-1",
        dependent_tasks=[],
        image="python:3.11",
        command=["python"],
        args=["-c", "print(1)"],
        inputs={"parameters": {"x": 10}}
    )
    changes = compare_task_properties(node1, node3)
    assert "image" in changes
    assert changes["image"]["before"] == "python:3.9"
    assert changes["image"]["after"] == "python:3.11"


def test_diff_pipelines():
    # Before tasks
    task_a_before = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_before = TaskNode("task-b", "comp-b", ["task-a"], "python:3.9")
    before = {"task-a": task_a_before, "task-b": task_b_before}

    # After tasks:
    # 1. task-a unchanged
    # 2. task-b modified (image changed)
    # 3. task-c added
    task_a_after = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_after = TaskNode("task-b", "comp-b", ["task-a"], "python:3.11")
    task_c_after = TaskNode("task-c", "comp-c", ["task-b"], "python:3.11")
    after = {"task-a": task_a_after, "task-b": task_b_after, "task-c": task_c_after}

    diff = diff_pipelines(before, after)

    assert diff.added_nodes == {"task-c"}
    assert diff.removed_nodes == set()
    assert diff.modified_nodes == {"task-b"}
    assert diff.unchanged_nodes == {"task-a"}

    assert ("task-a", "task-b") in diff.unchanged_edges
    assert ("task-b", "task-c") in diff.added_edges
    assert diff.removed_edges == set()


def test_task_rename_detection():
    # task-b is renamed to task-b-new, but retains component-ref comp-b
    task_a_before = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_before = TaskNode("task-b", "comp-b", ["task-a"], "python:3.9")
    before = {"task-a": task_a_before, "task-b": task_b_before}

    task_a_after = TaskNode("task-a", "comp-a", [], "python:3.9")
    task_b_after = TaskNode("task-b-new", "comp-b", ["task-a"], "python:3.9") # name changed, same component-ref
    after = {"task-a": task_a_after, "task-b-new": task_b_after}

    diff = diff_pipelines(before, after)

    assert diff.renamed_nodes == {"task-b": "task-b-new"}
    assert "task-b-new" in diff.modified_nodes
    assert "task-b" not in diff.removed_nodes
    assert "task-b-new" not in diff.added_nodes
    assert "rename" in diff.node_changes["task-b-new"]
    
    # Verify edges were mapped and classified as unchanged!
    assert ("task-a", "task-b-new") in diff.unchanged_edges
    assert diff.added_edges == set()
    assert diff.removed_edges == set()
