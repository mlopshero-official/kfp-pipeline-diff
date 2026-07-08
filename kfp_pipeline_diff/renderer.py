"""Renderer module for generating Mermaid diagrams and Markdown reports from PipelineDiffs.
"""

import json
from typing import Any, Dict, List, Optional
from .diff import PipelineDiff


def generate_mermaid_chart(diff: PipelineDiff) -> str:
    """Generates a color-coded Mermaid flowchart from a PipelineDiff.

    Args:
        diff: The PipelineDiff result.

    Returns:
        A string containing Mermaid flowchart markup.
    """
    lines = ["flowchart TD"]

    # 1. Define class styles
    lines.append("    classDef added fill:#e6f9ed,stroke:#1ea94c,stroke-width:2px,color:#1ea94c;")
    lines.append("    classDef removed fill:#ffebee,stroke:#ff1744,stroke-width:2px,stroke-dasharray: 5 5,color:#ff1744;")
    lines.append("    classDef modified fill:#fffde7,stroke:#ffb300,stroke-width:2px,color:#b78103;")
    lines.append("    classDef unchanged fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px,color:#616161;")
    lines.append("")

    # Combine all nodes to render
    all_nodes = {}
    for name, node in diff.after_nodes.items():
        all_nodes[name] = node
    for name, node in diff.before_nodes.items():
        if name not in all_nodes:
            all_nodes[name] = node

    # Create deterministic IDs mapped to sorted node names
    node_to_id = {}
    for i, name in enumerate(sorted(all_nodes.keys())):
        node_to_id[name] = f"node{i}"

    # Render nodes and categorize IDs for style assignments
    added_ids = []
    removed_ids = []
    modified_ids = []
    unchanged_ids = []

    for name in sorted(all_nodes.keys()):
        node = all_nodes[name]
        node_id = node_to_id[name]

        # Determine status and label
        if name in diff.added_nodes:
            label = f"[+] {name}"
            if node.is_subdag:
                label += " (Sub-DAG)"
            added_ids.append(node_id)
        elif name in diff.removed_nodes:
            label = f"[-] {name}"
            if node.is_subdag:
                label += " (Sub-DAG)"
            removed_ids.append(node_id)
        elif name in diff.modified_nodes:
            label = f"[*] {name}"
            if node.is_subdag:
                label += " (Sub-DAG)"
            modified_ids.append(node_id)
        else:
            label = name
            if node.is_subdag:
                label += " (Sub-DAG)"
            unchanged_ids.append(node_id)

        # Mermaid node formatting
        lines.append(f'    {node_id}["{label}"]')

    lines.append("")

    # Apply style classes to nodes
    if added_ids:
        lines.append(f"    class {','.join(added_ids)} added;")
    if removed_ids:
        lines.append(f"    class {','.join(removed_ids)} removed;")
    if modified_ids:
        lines.append(f"    class {','.join(modified_ids)} modified;")
    if unchanged_ids:
        lines.append(f"    class {','.join(unchanged_ids)} unchanged;")

    lines.append("")

    # Sort and render edges
    all_edges_to_render = []
    for parent, child in sorted(diff.unchanged_edges):
        all_edges_to_render.append((parent, child, "unchanged"))
    for parent, child in sorted(diff.added_edges):
        all_edges_to_render.append((parent, child, "added"))
    for parent, child in sorted(diff.removed_edges):
        all_edges_to_render.append((parent, child, "removed"))

    link_styles = []
    edge_index = 0

    for parent, child, status in all_edges_to_render:
        # Avoid rendering edges if either node isn't defined
        if parent in node_to_id and child in node_to_id:
            parent_id = node_to_id[parent]
            child_id = node_to_id[child]

            lines.append(f"    {parent_id} --> {child_id}")

            if status == "added":
                link_styles.append(f"    linkStyle {edge_index} stroke:#1ea94c,stroke-width:3px;")
            elif status == "removed":
                link_styles.append(f"    linkStyle {edge_index} stroke:#ff1744,stroke-width:2px,stroke-dasharray: 5 5;")
            else:
                link_styles.append(f"    linkStyle {edge_index} stroke:#9e9e9e,stroke-width:1px;")

            edge_index += 1

    lines.append("")
    lines.extend(link_styles)

    return "\n".join(lines)


def format_change_value(val: Any) -> str:
    """Formats raw values beautifully for markdown representation.

    Args:
        val: The raw property value.

    Returns:
        A markdown-formatted string.
    """
    if val is None:
        return "_None_"
    if isinstance(val, (list, tuple)):
        if not val:
            return "[]"
        return ", ".join(f"`{item}`" for item in val)
    if isinstance(val, dict):
        if not val:
            return "{}"
        # Nicely indent short JSON representations
        return f"<pre>{json.dumps(val, indent=2)}</pre>"
    return f"`{val}`"


def generate_markdown_report(diff: PipelineDiff, pr_number: Optional[int] = None) -> str:
    """Generates an HTML/Markdown report summarizing KFP pipeline changes.

    Args:
        diff: The PipelineDiff result.
        pr_number: Optional target Pull Request ID.

    Returns:
        The markdown body content.
    """
    mermaid_diagram = generate_mermaid_chart(diff)

    header = "## 🧬 KFP DAG Structure Diff"
    if pr_number:
        header += f" (PR #{pr_number})"

    # Summary table counts
    summary = f"""
| Change Type | Nodes (Tasks) | Edges (Dependencies) |
| :--- | :---: | :---: |
| 🟢 **Added** | {len(diff.added_nodes)} | {len(diff.added_edges)} |
| 🔴 **Removed** | {len(diff.removed_nodes)} | {len(diff.removed_edges)} |
| 🟡 **Modified** | {len(diff.modified_nodes)} | — |
| ⚪ **Unchanged** | {len(diff.unchanged_nodes)} | {len(diff.unchanged_edges)} |
"""

    diagram_section = f"""
<details open>
<summary><b>🗺️ Unified DAG Diagram</b></summary>

```mermaid
{mermaid_diagram}
```

_Legend: 🟢 green solid = added, 🔴 red dashed = removed, 🟡 amber solid = modified, ⚪ gray solid = unchanged_
</details>
"""

    detailed_changes = ""
    if diff.modified_nodes:
        details_list = []
        for name in sorted(diff.modified_nodes):
            changes = diff.node_changes[name]
            rows = []
            for prop, change in sorted(changes.items()):
                before_formatted = format_change_value(change["before"])
                after_formatted = format_change_value(change["after"])
                rows.append(f"| `{prop}` | {before_formatted} | {after_formatted} |")
            
            table_rows = "\n".join(rows)
            details_list.append(f"""
<details>
<summary>⚙️ <b>{name}</b></summary>

| Property | Before (Baseline) | After (Target) |
| :--- | :--- | :--- |
{table_rows}

</details>
""")
        
        detailed_changes = f"""
<details>
<summary><b>🔍 Detailed Task Property Changes</b></summary>

{"".join(details_list)}

</details>
"""

    # Combine everything including a sticky signature comment anchor
    report = f"""{header}
<!-- kfp-pipeline-diff-sticky-comment-anchor -->

### 📊 Summary Statistics
{summary}
{diagram_section}
{detailed_changes}
---
_Report generated by **kfp-pipeline-diff**_
"""
    return report
