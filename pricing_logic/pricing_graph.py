
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class TaskNode:
    key: str
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)  # e.g., "demo_complete" signal
    trade: str = "general"
    complexity_weight: float = 1.0

# Very small demo graph; extendable city-by-city and trade-by-trade
GRAPH: Dict[str, TaskNode] = {
    "demolition_tiles": TaskNode("demolition_tiles", requires=[], produces=["substrate_exposed"], trade="demo", complexity_weight=1.0),
    "plumbing_shower": TaskNode("plumbing_shower", requires=["substrate_exposed"], trade="plumbing", complexity_weight=1.1),
    "toilet_replace": TaskNode("toilet_replace", requires=["substrate_exposed"], trade="plumbing", complexity_weight=1.0),
    "vanity_install": TaskNode("vanity_install", requires=["substrate_exposed"], trade="carpentry", complexity_weight=1.0),
    "tiling_floor": TaskNode("tiling_floor", requires=["substrate_exposed"], trade="tiling", complexity_weight=1.1),
    "painting_walls": TaskNode("painting_walls", requires=[], trade="painting", complexity_weight=0.9),
}

def topo_sort(tasks: list[str]) -> list[str]:
    # basic topo: ensure 'requires' come before dependents when applicable
    order = []
    seen = set()
    remaining = set(tasks)
    guard = 0
    while remaining and guard < 100:
        progressed = False
        for t in list(remaining):
            node = GRAPH.get(t)
            if not node:
                order.append(t); remaining.remove(t); progressed = True; continue
            if all(req not in GRAPH or req in seen for req in node.requires):
                order.append(t)
                seen.add(t)
                remaining.remove(t)
                progressed = True
        if not progressed:
            # cycle or missing requirements: append remaining as-is
            order.extend(list(remaining))
            remaining.clear()
        guard += 1
    return order

def implied_requirements(tasks: list[str]) -> list[str]:
    # For any task that requires a signal, include the producer if absent
    to_add = []
    present = set(tasks)
    signals = {sig: t for t, n in GRAPH.items() for sig in n.produces}
    for t in tasks:
        node = GRAPH.get(t)
        if not node: 
            continue
        for req in node.requires:
            prod = signals.get(req)
            if prod and prod not in present:
                to_add.append(prod)
    return list(dict.fromkeys(to_add))
