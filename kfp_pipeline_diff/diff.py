"""Diff module for identifying added, removed, and modified nodes and edges in a KFP DAG.
"""

from typing import Any, Dict, List, Set, Tuple
from .parser import TaskNode

class PipelineDiff:
    """Contains the diff analysis results between two KFP pipelines."""

    def __init__(
        self,
        added_nodes: Set[str],
        removed_nodes: Set[str],
        modified_nodes: Set[str],
        unchanged_nodes: Set[str],
        node_changes: Dict[str, Dict[str, Dict[str, Any]]],
        added_edges: Set[Tuple[str, str]],
        removed_edges: Set[Tuple[str, str]],
        unchanged_edges: Set[Tuple[str, str]],
        before_nodes: Dict[str, TaskNode],
        after_nodes: Dict[str, TaskNode],
    ):
        self.added_nodes = added_nodes
        self.removed_nodes = removed_nodes
        self.modified_nodes = modified_nodes
        self.unchanged_nodes = unchanged_nodes
        self.node_changes = node_changes
        self.added_edges = added_edges
        self.removed_edges = removed_edges
        self.unchanged_edges = unchanged_edges
        self.before_nodes = before_nodes
        self.after_nodes = after_nodes


def compare_task_properties(before: TaskNode, after: TaskNode) -> Dict[str, Dict[str, Any]]:
    """Compares properties of two TaskNodes and returns the changes.

    Args:
        before: The baseline task node.
        after: The target task node.

    Returns:
        A dictionary mapping property names to changes: {"field": {"before": v1, "after": v2}}.
    """
    changes: Dict[str, Dict[str, Any]] = {}

    if before.image != after.image:
        changes["image"] = {"before": before.image, "after": after.image}

    if before.command != after.command:
        changes["command"] = {"before": before.command, "after": after.command}

    if before.args != after.args:
        changes["args"] = {"before": before.args, "after": after.args}

    if before.inputs != after.inputs:
        changes["inputs"] = {"before": before.inputs, "after": after.inputs}

    if before.component_ref != after.component_ref:
        changes["component_ref"] = {"before": before.component_ref, "after": after.component_ref}

    if before.is_subdag != after.is_subdag:
        changes["is_subdag"] = {"before": before.is_subdag, "after": after.is_subdag}

    return changes


def extract_edges(tasks: Dict[str, TaskNode]) -> Set[Tuple[str, str]]:
    """Extracts all parent -> child dependency edges from task definitions.

    Args:
        tasks: Dictionary mapping task name to its TaskNode.

    Returns:
        A set of directed edge tuples: (parent, child).
    """
    edges: Set[Tuple[str, str]] = set()
    for task_name, node in tasks.items():
        for dep in node.dependent_tasks:
            edges.add((dep, task_name))
    return edges


def diff_pipelines(
    before_tasks: Dict[str, TaskNode],
    after_tasks: Dict[str, TaskNode]
) -> PipelineDiff:
    """Reconciles two pipeline task mappings to classify node and edge changes.

    Args:
        before_tasks: Baseline task mappings.
        after_tasks: Target task mappings.

    Returns:
        A PipelineDiff result instance.
    """
    before_names = set(before_tasks.keys())
    after_names = set(after_tasks.keys())

    added_nodes = after_names - before_names
    removed_nodes = before_names - after_names
    common_nodes = before_names & after_names

    modified_nodes: Set[str] = set()
    unchanged_nodes: Set[str] = set()
    node_changes: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for name in common_nodes:
        changes = compare_task_properties(before_tasks[name], after_tasks[name])
        if changes:
            modified_nodes.add(name)
            node_changes[name] = changes
        else:
            unchanged_nodes.add(name)

    before_edges = extract_edges(before_tasks)
    after_edges = extract_edges(after_tasks)

    added_edges = after_edges - before_edges
    removed_edges = before_edges - after_edges
    unchanged_edges = before_edges & after_edges

    return PipelineDiff(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        modified_nodes=modified_nodes,
        unchanged_nodes=unchanged_nodes,
        node_changes=node_changes,
        added_edges=added_edges,
        removed_edges=removed_edges,
        unchanged_edges=unchanged_edges,
        before_nodes=before_tasks,
        after_nodes=after_tasks,
    )
