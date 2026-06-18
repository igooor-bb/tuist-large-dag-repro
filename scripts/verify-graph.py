#!/usr/bin/env python3
"""Verify that graph.json describes a valid acyclic Tuist dependency graph."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESETS = ("realistic", "stress")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify generated graph.json.")
    parser.add_argument("--preset", choices=PRESETS)
    parser.add_argument("--graph", default=str(ROOT / "graph.json"))
    return parser.parse_args()


def load_graph(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"graph file does not exist: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_adjacency(graph: dict) -> tuple[set[str], dict[str, list[str]], dict[str, int]]:
    nodes = {node["name"] for node in graph["nodes"]}
    adjacency = {name: [] for name in nodes}
    indegree = {name: 0 for name in nodes}
    seen_edges: set[tuple[str, str]] = set()
    errors: list[str] = []

    for edge in graph["edges"]:
        source = edge["from"]
        destination = edge["to"]
        if source not in nodes:
            errors.append(f"edge source does not exist: {source} -> {destination}")
            continue
        if destination not in nodes:
            errors.append(f"edge destination does not exist: {source} -> {destination}")
            continue
        if source == destination:
            errors.append(f"self-loop: {source}")
            continue
        key = (source, destination)
        if key in seen_edges:
            errors.append(f"duplicate edge: {source} -> {destination}")
            continue
        seen_edges.add(key)
        adjacency[source].append(destination)
        indegree[destination] += 1

    if errors:
        for error in errors[:50]:
            print(f"ERROR: {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"ERROR: ... and {len(errors) - 50} more", file=sys.stderr)
        raise SystemExit(1)

    return nodes, adjacency, indegree


def topological_order(
    nodes: set[str],
    adjacency: dict[str, list[str]],
    indegree: dict[str, int],
) -> list[str]:
    queue = deque(sorted(node for node in nodes if indegree[node] == 0))
    order: list[str] = []
    mutable_indegree = dict(indegree)

    while queue:
        node = queue.popleft()
        order.append(node)
        for dependency in adjacency[node]:
            mutable_indegree[dependency] -= 1
            if mutable_indegree[dependency] == 0:
                queue.append(dependency)

    if len(order) != len(nodes):
        cycle_nodes = sorted(node for node in nodes if mutable_indegree[node] > 0)
        print("ERROR: graph is cyclic; nodes remaining after Kahn sort:", file=sys.stderr)
        for node in cycle_nodes[:50]:
            print(f"  {node}", file=sys.stderr)
        if len(cycle_nodes) > 50:
            print(f"  ... and {len(cycle_nodes) - 50} more", file=sys.stderr)
        raise SystemExit(1)

    return order


def longest_path_length(order: list[str], adjacency: dict[str, list[str]]) -> int:
    distance = defaultdict(lambda: 1)
    best = 0
    for node in order:
        current = distance[node]
        if current > best:
            best = current
        for dependency in adjacency[node]:
            candidate = current + 1
            if candidate > distance[dependency]:
                distance[dependency] = candidate
    return best


def reachable_count(root: str, adjacency: dict[str, list[str]]) -> int:
    seen: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node])
    return len(seen)


def verify_range(name: str, value: int, thresholds: dict) -> None:
    minimum = thresholds.get(f"{name}_min")
    maximum = thresholds.get(f"{name}_max")
    label = name.replace("_", " ")
    if minimum is not None and value < minimum:
        raise SystemExit(f"{label} is {value}, expected at least {minimum}")
    if maximum is not None and value > maximum:
        raise SystemExit(f"{label} is {value}, expected at most {maximum}")


def verify_thresholds(
    graph: dict,
    nodes: set[str],
    order: list[str],
    adjacency: dict[str, list[str]],
) -> tuple[int, int]:
    thresholds = graph.get("thresholds", {})
    edge_count = len(graph["edges"])
    longest = longest_path_length(order, adjacency)
    verify_range("nodes", len(nodes), thresholds)
    verify_range("edges", edge_count, thresholds)
    verify_range("longest_path", longest, thresholds)

    app_reachable = reachable_count("App", adjacency)
    verify_range("app_reachable", app_reachable, thresholds)

    return longest, app_reachable


def main() -> None:
    args = parse_args()
    graph = load_graph(Path(args.graph))

    if args.preset and graph.get("preset") != args.preset:
        raise SystemExit(
            f"graph preset is {graph.get('preset')!r}, expected {args.preset!r}"
        )

    roots = graph.get("roots", [])
    for root in ("App", "AppUnitTests", "AppUITests"):
        if root not in roots:
            raise SystemExit(f"missing root in graph.json: {root}")

    nodes, adjacency, indegree = build_adjacency(graph)
    order = topological_order(nodes, adjacency, indegree)
    longest, app_reachable = verify_thresholds(graph, nodes, order, adjacency)

    print("OK: graph is acyclic and topologically sortable")
    print(f"preset: {graph.get('preset')}")
    print(f"nodes count: {len(nodes)}")
    print(f"edges count: {len(graph['edges'])}")
    print(f"longest path length: {longest}")
    print(f"App reachable nodes: {app_reachable}")


if __name__ == "__main__":
    main()
