#!/usr/bin/env python3
"""Generate a standalone Tuist workspace with a large acyclic target graph."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PRESETS = {
    "realistic": {
        "layers": 600,
        "width": 3,
        "foundation_count": 30,
        "shared_count": 170,
        "bridge_count": 20,
        "project_size": 25,
        "chain_span": 35,
        "infrastructure_chain_span": 20,
        "test_stride": 2,
        "thresholds": {
            "nodes_min": 2000,
            "nodes_max": 3000,
            "edges_min": 8000,
            "edges_max": 12000,
            "longest_path_min": 50,
            "longest_path_max": 150,
            "app_reachable_min": 200,
        },
    },
    "stress": {
        "layers": 1300,
        "width": 3,
        "foundation_count": 50,
        "shared_count": 220,
        "bridge_count": 25,
        "project_size": 25,
        "chain_span": 0,
        "infrastructure_chain_span": 0,
        "test_stride": 2,
        "thresholds": {
            "nodes_min": 3000,
            "nodes_max": 6000,
            "edges_min": 10000,
            "edges_max": 25000,
            "longest_path_min": 1000,
            "app_reachable_min": 1000,
        },
    },
}

DEFAULT_SEED = 5414363
APP_TARGETS = ("App", "AppUnitTests", "AppUITests")
PARAMETER_KEYS = (
    "layers",
    "width",
    "foundation_count",
    "shared_count",
    "bridge_count",
    "project_size",
    "chain_span",
    "infrastructure_chain_span",
    "test_stride",
)


@dataclass
class Node:
    name: str
    kind: str
    dependencies: list[str] = field(default_factory=list)
    project: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a large valid Tuist DAG fixture."
    )
    parser.add_argument("--preset", choices=sorted(PRESETS), default="realistic")
    parser.add_argument("--layers", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--foundation-count", type=int, dest="foundation_count")
    parser.add_argument("--shared-count", type=int, dest="shared_count")
    parser.add_argument("--bridge-count", type=int, dest="bridge_count")
    parser.add_argument("--project-size", type=int, dest="project_size")
    parser.add_argument("--chain-span", type=int, dest="chain_span")
    parser.add_argument("--infrastructure-chain-span", type=int, dest="infrastructure_chain_span")
    parser.add_argument("--test-stride", type=int, dest="test_stride")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def resolved_parameters(args: argparse.Namespace) -> dict[str, int]:
    params = dict(PRESETS[args.preset])
    params.pop("thresholds", None)
    for key in PARAMETER_KEYS:
        value = getattr(args, key)
        if value is not None:
            params[key] = value
    params["seed"] = args.seed

    for key in (
        "layers",
        "width",
        "foundation_count",
        "shared_count",
        "bridge_count",
        "project_size",
        "test_stride",
    ):
        if params[key] <= 0:
            raise SystemExit(f"{key.replace('_', '-')} must be positive")
    for key in ("chain_span", "infrastructure_chain_span"):
        if params[key] < 0:
            raise SystemExit(f"{key.replace('_', '-')} must be zero or positive")

    if params["bridge_count"] < 6:
        raise SystemExit("bridge-count must be at least 6")
    if params["shared_count"] < 2:
        raise SystemExit("shared-count must be at least 2")
    if params["foundation_count"] < 2:
        raise SystemExit("foundation-count must be at least 2")

    return params


def foundation_name(index: int) -> str:
    return f"Foundation{index:03d}"


def shared_name(index: int) -> str:
    return f"Shared{index:03d}"


def bridge_name(index: int) -> str:
    return f"Bridge{index:03d}"


def feature_prefix(index: int) -> str:
    return f"Feature{index:04d}"


def add_dependency(node: Node, dependency: str) -> None:
    if dependency == node.name:
        raise ValueError(f"self dependency for {node.name}")
    if dependency not in node.dependencies:
        node.dependencies.append(dependency)


def build_graph(params: dict[str, int]) -> list[Node]:
    random.seed(params["seed"])
    layers = params["layers"]
    width = params["width"]
    foundation_count = params["foundation_count"]
    shared_count = params["shared_count"]
    bridge_count = params["bridge_count"]
    chain_span = params["chain_span"]
    infrastructure_chain_span = params["infrastructure_chain_span"]
    test_stride = params["test_stride"]

    nodes: list[Node] = []
    by_name: dict[str, Node] = {}

    def add_node(name: str, kind: str) -> Node:
        if name in by_name:
            raise ValueError(f"duplicate node {name}")
        node = Node(name=name, kind=kind)
        nodes.append(node)
        by_name[name] = node
        return node

    def same_chain_segment(index: int, dependency_index: int, span: int) -> bool:
        if span == 0:
            return True
        return index // span == dependency_index // span

    for index in range(foundation_count):
        node = add_node(foundation_name(index), "foundation")
        if index > 0 and same_chain_segment(index, index - 1, infrastructure_chain_span):
            add_dependency(node, foundation_name(index - 1))
        if (
            index >= width
            and index % 5 == 0
            and same_chain_segment(index, index - width, infrastructure_chain_span)
        ):
            add_dependency(node, foundation_name(index - width))

    for index in range(shared_count):
        node = add_node(shared_name(index), "shared")
        add_dependency(node, foundation_name((index * 7 + params["seed"]) % foundation_count))
        if index > 0 and same_chain_segment(index, index - 1, infrastructure_chain_span):
            add_dependency(node, shared_name(index - 1))
        if (
            index >= width
            and index % 7 == 0
            and same_chain_segment(index, index - width, infrastructure_chain_span)
        ):
            add_dependency(node, shared_name(index - width))

    shared_tests_support = add_node("SharedTestsSupport", "shared-test-support")
    add_dependency(shared_tests_support, shared_name(shared_count - 1))
    add_dependency(shared_tests_support, foundation_name(foundation_count - 1))

    for index in range(bridge_count):
        node = add_node(bridge_name(index), "bridge")
        add_dependency(node, shared_name((index * 11 + 3) % shared_count))
        add_dependency(node, shared_name((index * 17 + 5) % shared_count))
        add_dependency(node, foundation_name((index * 13 + 1) % foundation_count))
        if index > 0 and index % 4 == 0:
            add_dependency(node, bridge_name(index - 1))

    test_indices = {index for index in range(layers) if index % test_stride == 0}
    test_indices.add(layers - 1)
    sorted_test_indices = sorted(test_indices)
    previous_test_index: dict[int, int | None] = {}
    last_seen_test_index: int | None = None
    for index in sorted_test_indices:
        previous_test_index[index] = last_seen_test_index
        last_seen_test_index = index

    for index in range(layers):
        prefix = feature_prefix(index)
        models = add_node(f"{prefix}Models", "feature-models")
        core = add_node(f"{prefix}Core", "feature-core")
        ui = add_node(f"{prefix}UI", "feature-ui")

        add_dependency(models, shared_name((index * 13 + 7) % shared_count))
        add_dependency(models, foundation_name((index * 5 + 3) % foundation_count))
        if index > 0 and same_chain_segment(index, index - 1, chain_span):
            add_dependency(models, f"{feature_prefix(index - 1)}Models")
        if (
            index >= width
            and index % 9 == 0
            and same_chain_segment(index, index - width, chain_span)
        ):
            add_dependency(models, f"{feature_prefix(index - width)}Models")

        add_dependency(core, models.name)
        add_dependency(core, shared_name((index * 17 + 11) % shared_count))
        add_dependency(core, bridge_name(1))
        if index % 3 == 0:
            add_dependency(core, bridge_name(2))
        if index % 4 == 0:
            add_dependency(core, bridge_name(4))
        if index > 0 and same_chain_segment(index, index - 1, chain_span):
            add_dependency(core, f"{feature_prefix(index - 1)}Core")
        if (
            index >= width
            and index % 6 == 0
            and same_chain_segment(index, index - width, chain_span)
        ):
            add_dependency(core, f"{feature_prefix(index - width)}Models")

        add_dependency(ui, core.name)
        add_dependency(ui, shared_name((index * 19 + 13) % shared_count))
        add_dependency(ui, bridge_name(0))
        if index % 2 == 0:
            add_dependency(ui, bridge_name(2))
        if index % 5 == 0:
            add_dependency(ui, bridge_name(3))
        if index > 0 and same_chain_segment(index, index - 1, chain_span):
            add_dependency(ui, f"{feature_prefix(index - 1)}UI")
        if (
            index >= width
            and index % 8 == 0
            and same_chain_segment(index, index - width, chain_span)
        ):
            add_dependency(ui, f"{feature_prefix(index - width)}Core")

        if index in test_indices:
            tests_support = add_node(f"{prefix}TestsSupport", "feature-test-support")
            tests = add_node(f"{prefix}Tests", "feature-tests")

            add_dependency(tests_support, models.name)
            add_dependency(tests_support, shared_tests_support.name)
            if index % 3 == 0:
                add_dependency(tests_support, bridge_name(5))
            previous_index = previous_test_index[index]
            if (
                previous_index is not None
                and index % 4 == 0
                and same_chain_segment(index, previous_index, chain_span)
            ):
                add_dependency(tests_support, f"{feature_prefix(previous_index)}TestsSupport")

            add_dependency(tests, ui.name)
            add_dependency(tests, tests_support.name)
            add_dependency(tests, shared_tests_support.name)
            if previous_index is not None and same_chain_segment(index, previous_index, chain_span):
                add_dependency(tests, f"{feature_prefix(previous_index)}Tests")

    app = add_node("App", "app")
    recent_features = {
        layers - 1,
        max(0, layers - 1 - max(1, layers // 35)),
        max(0, layers - 1 - max(1, layers // 20)),
        max(0, layers - 1 - max(1, layers // 12)),
    }
    for index in sorted(recent_features, reverse=True):
        add_dependency(app, f"{feature_prefix(index)}UI")
    for index in range(bridge_count):
        add_dependency(app, bridge_name(index))
    add_dependency(app, shared_tests_support.name)

    app_unit_tests = add_node("AppUnitTests", "app-tests")
    add_dependency(app_unit_tests, app.name)
    add_dependency(app_unit_tests, f"{feature_prefix(layers - 1)}Tests")
    secondary_test_index = max(index for index in sorted_test_indices if index <= max(0, layers - 1 - width))
    add_dependency(app_unit_tests, f"{feature_prefix(secondary_test_index)}Tests")
    add_dependency(app_unit_tests, shared_tests_support.name)

    app_ui_tests = add_node("AppUITests", "app-ui-tests")
    add_dependency(app_ui_tests, app.name)
    add_dependency(app_ui_tests, f"{feature_prefix(layers - 1)}UI")
    add_dependency(app_ui_tests, f"{feature_prefix(layers - 1)}TestsSupport")
    add_dependency(app_ui_tests, shared_tests_support.name)

    unknown_dependencies = sorted(
        {
            dependency
            for node in nodes
            for dependency in node.dependencies
            if dependency not in by_name
        }
    )
    if unknown_dependencies:
        raise ValueError(f"unknown dependencies: {unknown_dependencies[:10]}")

    return nodes


def assign_projects(nodes: list[Node], project_size: int) -> list[str]:
    shard_names: list[str] = []
    shard_index = 0
    shard_target_count = 0
    for node in nodes:
        if node.name in APP_TARGETS:
            node.project = "App"
            continue
        if shard_target_count == 0:
            shard_names.append(f"Shard{shard_index:03d}")
        node.project = shard_names[-1]
        shard_target_count += 1
        if shard_target_count == project_size:
            shard_index += 1
            shard_target_count = 0
    return shard_names


def remove_generated_fixture() -> None:
    for relative in ("Workspace.swift", "graph.json"):
        path = ROOT / relative
        if path.exists():
            path.unlink()

    projects = ROOT / "Projects"
    if projects.exists():
        shutil.rmtree(projects)


def swift_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def target_dependency_expression(
    source_project: str,
    dependency: str,
    project_by_target: dict[str, str],
) -> str:
    dependency_project = project_by_target[dependency]
    if dependency_project == source_project:
        return f".target(name: {swift_string(dependency)})"
    return (
        f".project(target: {swift_string(dependency)}, "
        f"path: {swift_string('../' + dependency_project)})"
    )


def write_workspace(projects: list[str]) -> None:
    project_lines = ",\n".join(f"        {swift_string('Projects/' + project)}" for project in projects)
    contents = f"""import ProjectDescription

let workspace = Workspace(
    name: "TuistLargeDAGRepro",
    projects: [
{project_lines}
    ]
)
"""
    (ROOT / "Workspace.swift").write_text(contents, encoding="utf-8")


def write_project(
    project_name: str,
    targets: list[Node],
    project_by_target: dict[str, str],
) -> None:
    project_dir = ROOT / "Projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    target_blocks: list[str] = []
    for target in targets:
        source_dir = project_dir / "Sources" / target.name
        source_dir.mkdir(parents=True, exist_ok=True)
        marker_name = f"{target.name}Marker"
        source = f"""public enum {marker_name} {{
    public static let value = {swift_string(target.name)}
}}
"""
        (source_dir / f"{target.name}.swift").write_text(source, encoding="utf-8")

        if target.dependencies:
            dependency_lines = ",\n".join(
                "                "
                + target_dependency_expression(project_name, dependency, project_by_target)
                for dependency in target.dependencies
            )
            dependencies = f"""[
{dependency_lines}
            ]"""
        else:
            dependencies = "[]"

        target_blocks.append(
            f"""        .target(
            name: {swift_string(target.name)},
            destinations: .iOS,
            product: .framework,
            bundleId: {swift_string('io.tuist.large-dag-repro.' + target.name.lower())},
            deploymentTargets: .iOS("15.0"),
            infoPlist: .default,
            sources: [{swift_string('Sources/' + target.name + '/**')}],
            dependencies: {dependencies}
        )"""
        )

    targets_contents = ",\n".join(target_blocks)
    contents = f"""import ProjectDescription

let project = Project(
    name: {swift_string(project_name)},
    targets: [
{targets_contents}
    ]
)
"""
    (project_dir / "Project.swift").write_text(contents, encoding="utf-8")


def write_projects(nodes: list[Node], shard_names: list[str]) -> None:
    projects = ["App", *shard_names]
    project_by_target = {node.name: node.project for node in nodes if node.project is not None}
    nodes_by_project: dict[str, list[Node]] = {project: [] for project in projects}
    app_order = {name: index for index, name in enumerate(APP_TARGETS)}

    for node in nodes:
        if node.project is None:
            raise ValueError(f"node {node.name} has no project")
        nodes_by_project[node.project].append(node)

    nodes_by_project["App"].sort(key=lambda node: app_order[node.name])

    write_workspace(projects)
    for project in projects:
        write_project(project, nodes_by_project[project], project_by_target)


def write_graph_json(
    preset: str,
    params: dict[str, int],
    nodes: list[Node],
    shard_names: list[str],
) -> None:
    edges = [
        {"from": node.name, "to": dependency}
        for node in nodes
        for dependency in node.dependencies
    ]
    thresholds = dict(PRESETS[preset]["thresholds"])
    reproduction = {
        "default_command": "tuist generate --no-open",
        "focused_command": "tuist generate --no-open App",
        "focused_target": "App",
        "repeat_existing_dsl_check": True,
    }
    if preset == "realistic":
        reproduction["expected_unpatched"] = "should not crash before generation"
    else:
        reproduction["expected_unpatched"] = "default command first exposes CircularDependencyLinter, then later recursive graph-processing risks as fixes are applied; focused command may expose FocusTargetsGraphMappers.topologicalSort"
    graph = {
        "preset": preset,
        "parameters": params,
        "roots": list(APP_TARGETS),
        "thresholds": thresholds,
        "reproduction": reproduction,
        "projects": ["App", *shard_names],
        "nodes": [
            {
                "name": node.name,
                "kind": node.kind,
                "project": node.project,
                "path": f"Projects/{node.project}/Sources/{node.name}/{node.name}.swift",
            }
            for node in nodes
        ],
        "edges": edges,
    }
    (ROOT / "graph.json").write_text(
        json.dumps(graph, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def print_summary(preset: str, params: dict[str, int], nodes: list[Node], shard_names: list[str]) -> None:
    edge_count = sum(len(node.dependencies) for node in nodes)
    print(f"Generated preset: {preset}")
    print(f"Layers: {params['layers']}")
    print(f"Width: {params['width']}")
    print(f"Chain span: {params['chain_span'] or 'unbounded'}")
    print(f"Infrastructure chain span: {params['infrastructure_chain_span'] or 'unbounded'}")
    print(f"Targets: {len(nodes)}")
    print(f"Edges: {edge_count}")
    print(f"Projects: {1 + len(shard_names)}")
    print("Run: python3 scripts/verify-graph.py")


def main() -> None:
    args = parse_args()
    params = resolved_parameters(args)
    nodes = build_graph(params)
    shard_names = assign_projects(nodes, params["project_size"])
    remove_generated_fixture()
    write_projects(nodes, shard_names)
    write_graph_json(args.preset, params, nodes, shard_names)
    print_summary(args.preset, params, nodes, shard_names)


if __name__ == "__main__":
    main()
