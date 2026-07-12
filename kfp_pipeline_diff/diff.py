"""Diff module for identifying added, removed, and modified nodes and edges in a KFP DAG.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
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
        before_name: str = "unnamed-pipeline",
        after_name: str = "unnamed-pipeline",
        added_parameters: Optional[Set[str]] = None,
        removed_parameters: Optional[Set[str]] = None,
        modified_parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        before_parameters: Optional[Dict[str, Any]] = None,
        after_parameters: Optional[Dict[str, Any]] = None,
        renamed_nodes: Optional[Dict[str, str]] = None,
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
        self.before_name = before_name
        self.after_name = after_name
        self.added_parameters = added_parameters or set()
        self.removed_parameters = removed_parameters or set()
        self.modified_parameters = modified_parameters or {}
        self.before_parameters = before_parameters or {}
        self.after_parameters = after_parameters or {}
        self.renamed_nodes = renamed_nodes or {}


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
    after_tasks: Dict[str, TaskNode],
    before_name: str = "unnamed-pipeline",
    after_name: str = "unnamed-pipeline",
    before_params: Optional[Dict[str, Any]] = None,
    after_params: Optional[Dict[str, Any]] = None,
) -> PipelineDiff:
    """Reconciles two pipeline task mappings to classify node and edge changes.

    Args:
        before_tasks: Baseline task mappings.
        after_tasks: Target task mappings.
        before_name: The extracted baseline pipeline name.
        after_name: The extracted target pipeline name.
        before_params: Optional baseline pipeline input parameters.
        after_params: Optional target pipeline input parameters.

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

    # Rename detection heuristic
    renamed_nodes: Dict[str, str] = {}  # old_name -> new_name
    matched_added = set()

    for r_name in sorted(list(removed_nodes)):
        r_node = before_tasks[r_name]
        for a_name in sorted(list(added_nodes)):
            if a_name in matched_added:
                continue
            a_node = after_tasks[a_name]
            
            is_match = False
            if r_node.component_ref and r_node.component_ref == a_node.component_ref:
                is_match = True
            elif r_node.image and r_node.image == a_node.image and r_node.command == a_node.command and r_node.is_subdag == a_node.is_subdag:
                is_match = True
                
            if is_match:
                renamed_nodes[r_name] = a_name
                matched_added.add(a_name)
                break

    # Adjust added/removed sets based on renames
    for r_name, a_name in renamed_nodes.items():
        removed_nodes.remove(r_name)
        added_nodes.remove(a_name)
        
        # Add to modified nodes & compare properties
        changes = compare_task_properties(before_tasks[r_name], after_tasks[a_name])
        changes["rename"] = {"before": r_name, "after": a_name}
        
        modified_nodes.add(a_name)
        node_changes[a_name] = changes

    before_edges = extract_edges(before_tasks)
    after_edges = extract_edges(after_tasks)

    # Map before_edges using renamed names to avoid artificial edge added/removed reports
    normalized_before_edges = set()
    for parent, child in before_edges:
        p_mapped = renamed_nodes.get(parent, parent)
        c_mapped = renamed_nodes.get(child, child)
        normalized_before_edges.add((p_mapped, c_mapped))

    added_edges = after_edges - normalized_before_edges
    removed_edges = normalized_before_edges - after_edges
    unchanged_edges = normalized_before_edges & after_edges

    # Reconcile pipeline-level input parameters
    before_p = before_params or {}
    after_p = after_params or {}

    before_p_names = set(before_p.keys())
    after_p_names = set(after_p.keys())

    added_parameters = after_p_names - before_p_names
    removed_parameters = before_p_names - after_p_names
    common_params = before_p_names & after_p_names

    modified_parameters: Dict[str, Dict[str, Any]] = {}
    for p_name in sorted(common_params):
        bp_val = before_p[p_name]
        ap_val = after_p[p_name]
        
        p_changes = {}
        if isinstance(bp_val, dict) and isinstance(ap_val, dict):
            if bp_val.get("parameterType") != ap_val.get("parameterType"):
                p_changes["parameterType"] = {"before": bp_val.get("parameterType"), "after": ap_val.get("parameterType")}
            if bp_val.get("defaultValue") != ap_val.get("defaultValue"):
                p_changes["defaultValue"] = {"before": bp_val.get("defaultValue"), "after": ap_val.get("defaultValue")}
        elif bp_val != ap_val:
            p_changes["value"] = {"before": bp_val, "after": ap_val}
            
        if p_changes:
            modified_parameters[p_name] = p_changes

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
        before_name=before_name,
        after_name=after_name,
        added_parameters=added_parameters,
        removed_parameters=removed_parameters,
        modified_parameters=modified_parameters,
        before_parameters=before_p,
        after_parameters=after_p,
        renamed_nodes=renamed_nodes,
    )
