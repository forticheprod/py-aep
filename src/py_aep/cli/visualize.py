"""
Visualize an After Effects project structure.

Supports multiple output formats:
- text: ASCII tree in terminal
- dot: Graphviz DOT format (can be rendered with `dot -Tpng output.dot -o output.png`)
- mermaid: Mermaid flowchart (embeddable in markdown)
- json: JSON hierarchy (for custom processing)

Usage:
    aep-visualize project.aep
    aep-visualize project.aep --format dot > project.dot
    aep-visualize project.aep --format mermaid
    aep-visualize project.aep --depth 2
    aep-visualize project.aep --no-properties
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from py_aep import parse

from ..models.items.composition import CompItem
from ..models.items.folder import FolderItem
from ..models.items.footage import FootageItem
from ..models.properties.property_group import PropertyGroup

if TYPE_CHECKING:
    from typing import Any, Generator, TextIO

    from ..models.application import Application
    from ..models.items.item import Item
    from ..models.layers.layer import Layer
    from ..models.project import Project
    from ..models.properties.property import Property
    from ..models.renderqueue.output_module import OutputModule
    from ..models.renderqueue.render_queue_item import RenderQueueItem

# =============================================================================
# Node builders - Convert model objects to a uniform dict structure
# =============================================================================


def build_project_node(
    app: Application, include_properties: bool = True
) -> dict[str, Any]:
    """Build the root project node."""
    project = app.project
    attrs: dict[str, Any] = {
        "version": app.version,
        "build_number": app.build_number,
        "bits_per_channel": project.bits_per_channel.name,
        "expression_engine": project.expression_engine,
    }
    if project.effect_names:
        attrs["effects_used"] = len(project.effect_names)

    children: list[dict[str, Any]] = []
    root = project.root_folder
    for item in root:
        children.append(build_item_node(item, project, include_properties))

    # Add render queue if it has items
    if project.render_queue is None:
        raise RuntimeError("Project render_queue should not be None")
    if project.render_queue.items:
        children.append(build_render_queue_node(project))

    return {
        "type": "Project",
        "name": Path(project.file).name,
        "attrs": attrs,
        "children": children,
    }


def build_item_node(
    item: Item, project: Project, include_properties: bool = True
) -> dict[str, Any]:
    """Build a node for any item type."""
    if isinstance(item, FolderItem):
        return build_folder_node(item, project, include_properties)
    elif isinstance(item, CompItem):
        return build_comp_node(item, project, include_properties)
    elif isinstance(item, FootageItem):
        return build_footage_node(item)
    else:
        return {
            "type": "Item",
            "name": item.name,
            "attrs": {"type_name": item.type_name},
            "children": [],
        }


def build_folder_node(
    folder: FolderItem, project: Project, include_properties: bool = True
) -> dict[str, Any]:
    """Build a folder node with its children."""
    children: list[dict[str, Any]] = []
    for item in folder:
        children.append(build_item_node(item, project, include_properties))

    return {
        "type": "Folder",
        "name": folder.name,
        "attrs": {"label": folder.label.name.lower() if folder.label.value else None},
        "children": children,
    }


def build_comp_node(
    comp: CompItem, project: Project, include_properties: bool = True
) -> dict[str, Any]:
    """Build a composition node with layers."""
    attrs: dict[str, Any] = {
        "size": f"{comp.width}x{comp.height}",
        "duration": f"{comp.duration:.2f}s",
        "frame_rate": comp.frame_rate,
        "layers_count": len(comp.layers),
    }
    if comp.markers:
        attrs["markers"] = len(comp.markers)

    children: list[dict[str, Any]] = []
    for layer in comp.layers:
        children.append(build_layer_node(layer, project, include_properties))

    return {
        "type": "Composition",
        "name": comp.name,
        "attrs": attrs,
        "children": children,
    }


def build_footage_node(footage: FootageItem) -> dict[str, Any]:
    """Build a footage item node."""
    attrs: dict[str, Any] = {
        "asset_type": footage.asset_type,
        "size": f"{footage.width}x{footage.height}",
    }
    if footage.duration > 0:
        attrs["duration"] = f"{footage.duration:.2f}s"
    if footage.file:
        attrs["file"] = Path(footage.file).name

    return {
        "type": "Footage",
        "name": footage.name,
        "attrs": attrs,
        "children": [],
    }


def build_layer_node(
    layer: Layer, project: Project, include_properties: bool = True
) -> dict[str, Any]:
    """Build a layer node with properties."""
    attrs: dict[str, Any] = {
        "type": layer.layer_type,
        "enabled": layer.enabled,
    }
    if not layer.enabled:
        attrs["enabled"] = False
    if layer.null_layer:
        attrs["null"] = True
    if layer.parent:
        attrs["parent"] = layer.parent.name
    if layer.markers:
        attrs["markers"] = len(layer.markers)

    children: list[dict[str, Any]] = []
    if include_properties:
        # Transform properties
        if layer.transform:
            children.append(build_property_group_node(layer.transform))

        # Effects
        if layer.effects:
            children.append(build_property_group_node(layer.effects))

        # Text properties
        if isinstance(layer.text, PropertyGroup):
            children.append(build_property_group_node(layer.text))

    return {
        "type": "Layer",
        "name": layer.name or "(unnamed)",
        "attrs": attrs,
        "children": children,
    }


def build_property_group_node(group: PropertyGroup) -> dict[str, Any]:
    """Build a property group node."""
    attrs: dict[str, bool] = {}
    if group.is_effect:
        attrs["effect"] = True

    children = [build_property_or_group_node(p) for p in group.properties]

    return {
        "type": "PropertyGroup",
        "name": group.name,
        "attrs": attrs,
        "children": children,
    }


def build_property_or_group_node(prop: Property | PropertyGroup) -> dict[str, Any]:
    """Build a property or property group node."""
    if isinstance(prop, PropertyGroup):
        return build_property_group_node(prop)
    return build_property_node(prop)


def build_property_node(prop: Property) -> dict[str, Any]:
    """Build a property node."""
    attrs: dict[str, Any] = {}
    if prop._animated:
        attrs["animated"] = True
        attrs["keyframes"] = len(prop.keyframes)
    if prop.expression_enabled and prop.expression:
        attrs["expression"] = True
    if prop.value is not None and not prop._animated:
        # Format value for display
        if isinstance(prop.value, (list, tuple)):
            if len(prop.value) <= 4:
                attrs["value"] = prop.value
        elif isinstance(prop.value, float):
            attrs["value"] = round(prop.value, 2)
        else:
            attrs["value"] = prop.value

    return {
        "type": "Property",
        "name": prop.name,
        "attrs": attrs,
        "children": [],
    }


def build_render_queue_node(project: Project) -> dict[str, Any]:
    """Build a render queue node with its items."""
    if project.render_queue is None:
        raise RuntimeError("Project render_queue should not be None")
    attrs: dict[str, Any] = {
        "items": len(project.render_queue.items),
    }

    children: list[dict[str, Any]] = []
    for i, item in enumerate(project.render_queue.items):
        children.append(build_render_queue_item_node(item, i + 1, project))

    return {
        "type": "RenderQueue",
        "name": "Render Queue",
        "attrs": attrs,
        "children": children,
    }


def build_render_queue_item_node(
    item: RenderQueueItem, index: int, project: Project
) -> dict[str, Any]:
    """Build a render queue item node with output modules."""
    attrs: dict[str, Any] = {
        "output_modules": len(item.output_modules),
    }

    # Try to find the comp name
    comp = item.comp
    attrs["comp"] = getattr(comp, "name", None)

    children: list[dict[str, Any]] = []
    for om in item.output_modules:
        children.append(build_output_module_node(om))

    return {
        "type": "RenderQueueItem",
        "name": f"Item {index}",
        "attrs": attrs,
        "children": children,
    }


def build_output_module_node(om: OutputModule) -> dict[str, Any]:
    """Build an output module node."""
    attrs: dict[str, Any] = {}
    if om.file:
        attrs["file"] = Path(om.file).name
    if om.file_template:
        attrs["name_template"] = om.file_template

    return {
        "type": "OutputModule",
        "name": "Output Module",
        "attrs": attrs,
        "children": [],
    }


# =============================================================================
# Output formatters
# =============================================================================


def format_text(
    node: dict[str, Any],
    output: TextIO,
    prefix: str = "",
    is_last: bool = True,
    max_depth: int | None = None,
    current_depth: int = 0,
) -> None:
    """Output as ASCII tree."""
    if max_depth is not None and current_depth > max_depth:
        return

    # Determine connector
    connector = "└── " if is_last else "├── "
    if current_depth == 0:
        connector = ""

    # Format node line
    type_icon = {
        "Project": "📦",
        "Folder": "📁",
        "Composition": "🎬",
        "Footage": "🎞️",
        "Layer": "📄",
        "PropertyGroup": "📂",
        "Property": "⚙️",
        "Transform": "🔄",
        "RenderQueue": "🎯",
        "RenderQueueItem": "📋",
        "OutputModule": "💾",
    }.get(node["type"], "•")

    attrs_str = ""
    if node.get("attrs"):
        # Filter out None values
        filtered = {k: v for k, v in node["attrs"].items() if v is not None}
        if filtered:
            attrs_str = " " + str(filtered)

    output.write(f"{prefix}{connector}{type_icon} {node['name']}{attrs_str}\n")

    # Process children
    children = node.get("children", [])
    child_prefix = prefix + ("    " if is_last else "│   ")
    if current_depth == 0:
        child_prefix = ""

    for i, child in enumerate(children):
        is_last_child = i == len(children) - 1
        format_text(
            child, output, child_prefix, is_last_child, max_depth, current_depth + 1
        )


def format_dot(
    node: dict[str, Any],
    output: TextIO,
    max_depth: int | None = None,
) -> None:
    """Output as Graphviz DOT format."""
    output.write("digraph AEProject {\n")
    output.write("    rankdir=TB;\n")
    output.write('    node [shape=record, fontname="Helvetica", fontsize=10];\n')
    output.write("    edge [fontsize=8];\n")
    output.write("\n")

    node_id = [0]  # Use list for mutable counter in nested function

    def get_node_id() -> str:
        node_id[0] += 1
        return f"n{node_id[0]}"

    def escape_dot(s: str) -> str:
        """Escape special characters for DOT labels."""
        return (
            s.replace('"', '\\"')
            .replace("<", "\\<")
            .replace(">", "\\>")
            .replace("|", "\\|")
        )

    def write_node(
        n: dict[str, Any], parent_id: str | None = None, depth: int = 0
    ) -> str:
        if max_depth is not None and depth > max_depth:
            return ""

        nid = get_node_id()

        # Color based on type
        colors: dict[str, str] = {
            "Project": "#4a90d9",
            "Folder": "#f5a623",
            "Composition": "#7ed321",
            "Footage": "#9b59b6",
            "Layer": "#3498db",
            "PropertyGroup": "#95a5a6",
            "Property": "#bdc3c7",
            "Transform": "#1abc9c",
        }
        color = colors.get(n["type"], "#cccccc")

        # Build label
        name = escape_dot(n["name"])
        attrs = n.get("attrs", {})
        attrs_lines = []
        for k, v in attrs.items():
            if v is not None:
                attrs_lines.append(f"{k}: {escape_dot(str(v))}")

        if attrs_lines:
            label = (
                "{{" + n["type"] + "|" + name + "|" + "\\l".join(attrs_lines) + "\\l}}"
            )
        else:
            label = "{{" + n["type"] + "|" + name + "}}"

        output.write(
            f'    {nid} [label="{label}", style=filled, fillcolor="{color}"];\n'
        )

        if parent_id:
            output.write(f"    {parent_id} -> {nid};\n")

        for child in n.get("children", []):
            write_node(child, nid, depth + 1)

        return nid

    write_node(node)
    output.write("}\n")


def format_mermaid(
    node: dict[str, Any],
    output: TextIO,
    max_depth: int | None = None,
) -> None:
    """Output as Mermaid flowchart."""
    output.write("```mermaid\nflowchart TD\n")

    node_id = [0]

    def get_node_id() -> str:
        node_id[0] += 1
        return f"n{node_id[0]}"

    def escape_mermaid(s: str) -> str:
        """Escape special characters for Mermaid."""
        return s.replace('"', "'").replace("<", "‹").replace(">", "›")

    def write_node(
        n: dict[str, Any], parent_id: str | None = None, depth: int = 0
    ) -> str:
        if max_depth is not None and depth > max_depth:
            return ""

        nid = get_node_id()
        name = escape_mermaid(n["name"])
        node_type = n["type"]

        # Different shapes for different types
        if node_type == "Project":
            shape = f'{nid}[["🎬 {name}"]]'
        elif node_type == "Folder":
            shape = f'{nid}[/"📁 {name}"/]'
        elif node_type == "Composition":
            shape = f'{nid}[("🎬 {name}")]'
        elif node_type == "Footage":
            shape = f'{nid}[("🎞️ {name}")]'
        elif node_type == "Layer":
            shape = f'{nid}["📄 {name}"]'
        else:
            shape = f'{nid}("{name}")'

        output.write(f"    {shape}\n")

        if parent_id:
            output.write(f"    {parent_id} --> {nid}\n")

        for child in n.get("children", []):
            write_node(child, nid, depth + 1)

        return nid

    write_node(node)
    output.write("```\n")


def format_json(
    node: dict[str, Any],
    output: TextIO,
    max_depth: int | None = None,
) -> None:
    """Output as JSON."""

    def filter_depth(n: dict[str, Any], depth: int = 0) -> dict[str, Any]:
        if max_depth is not None and depth >= max_depth:
            result = dict(n)
            if result.get("children"):
                result["children"] = f"[{len(result['children'])} children omitted]"
            return result

        result = dict(n)
        if result.get("children"):
            result["children"] = [
                filter_depth(c, depth + 1) for c in result["children"]
            ]
        return result

    filtered = filter_depth(node)
    output.write(json.dumps(filtered, indent=2, default=str))
    output.write("\n")


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """CLI entry point for aep-visualize command."""
    parser = argparse.ArgumentParser(
        prog="aep-visualize",
        description="Visualize an After Effects project structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s project.aep
  %(prog)s project.aep --format dot > project.dot
  %(prog)s project.aep --format mermaid
  %(prog)s project.aep --depth 2 --no-properties
        """,
    )
    parser.add_argument("aep_file", help="Path to the .aep file")
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "dot", "mermaid", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--depth",
        "-d",
        type=int,
        default=None,
        help="Maximum depth to display (default: unlimited)",
    )
    parser.add_argument(
        "--no-properties",
        action="store_true",
        help="Exclude layer properties from output",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file (default: stdout)",
    )

    args = parser.parse_args()

    aep_path = Path(args.aep_file)
    if not aep_path.exists():
        print(f"Error: File not found: {aep_path}", file=sys.stderr)
        return 1

    app = parse(aep_path)

    include_properties = not args.no_properties
    root_node = build_project_node(app, include_properties)

    # Output using context manager
    output_path = Path(args.output) if args.output else None

    @contextlib.contextmanager
    def get_output() -> Generator[TextIO, None, None]:
        if output_path:
            with output_path.open("w", encoding="utf-8") as f:
                yield f
        else:
            yield sys.stdout

    with get_output() as output:
        if args.format == "text":
            format_text(root_node, output, max_depth=args.depth)
        elif args.format == "dot":
            format_dot(root_node, output, max_depth=args.depth)
        elif args.format == "mermaid":
            format_mermaid(root_node, output, max_depth=args.depth)
        elif args.format == "json":
            format_json(root_node, output, max_depth=args.depth)

    return 0


if __name__ == "__main__":
    sys.exit(main())
