#!/usr/bin/env python3
"""Print statistics for the generated graph.json fixture."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print graph statistics.")
    parser.add_argument("--graph", default=str(ROOT / "graph.json"))
    return parser.parse_args()


def load_graph(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"graph file does not exist: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_graph(graph: dict) -> tuple[set[str], dict[str, list[str]], dict[str, int], dict[str, int]]:
    nodes = {node["name"] for node in graph["nodes"]}
    adjacency = {name: [] for name in nodes}
    indegree = {name: 0 for name in nodes}
    outdegree = {name: 0 for name in nodes}
    for edge in graph["edges"]:
        source = edge["from"]
        destination = edge["to"]
        adjacency[source].append(destination)
        indegree[destination] += 1
        outdegree[source] += 1
    return nodes, adjacency, indegree, outdegree


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
        raise SystemExit("graph is cyclic; run scripts/verify-graph.py for details")
    return order


def longest_path_length(order: list[str], adjacency: dict[str, list[str]]) -> int:
    distance = defaultdict(lambda: 1)
    best = 0
    for node in order:
        current = distance[node]
        best = max(best, current)
        for dependency in adjacency[node]:
            distance[dependency] = max(distance[dependency], current + 1)
    return best


def print_top(title: str, values: dict[str, int]) -> None:
    print(title)
    for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:20]:
        print(f"  {count:6d}  {name}")


def main() -> None:
    args = parse_args()
    graph = load_graph(Path(args.graph))
    nodes, adjacency, indegree, outdegree = build_graph(graph)
    order = topological_order(nodes, adjacency, indegree)
    longest = longest_path_length(order, adjacency)

    print(f"preset: {graph.get('preset')}")
    print(f"nodes count: {len(nodes)}")
    print(f"edges count: {len(graph['edges'])}")
    print(f"longest path length: {longest}")
    print(f"max in-degree: {max(indegree.values())}")
    print(f"max out-degree: {max(outdegree.values())}")
    print()
    print_top("top 20 fan-in nodes:", indegree)
    print()
    print_top("top 20 fan-out nodes:", outdegree)


if __name__ == "__main__":
    main()
