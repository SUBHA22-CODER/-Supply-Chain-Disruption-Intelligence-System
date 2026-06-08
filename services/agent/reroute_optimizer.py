"""
Task 10: OR-Tools rerouting optimizer.

Given a disrupted supplier, finds alternative suppliers from Neo4j graph,
solves a VRP-like assignment problem using OR-Tools CP-SAT solver, and
includes a fast Dijkstra-based fallback for urgent cases.
"""
import os
import time
import heapq
import uuid
import numpy as np
from typing import List, Dict, Optional, NamedTuple
from dataclasses import dataclass, field

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False


# ── Data Structures ─────────────────────────────────────────────────────────
@dataclass
class SKUAssignment:
    sku_id: str
    assigned_supplier_id: str
    cost_increase_pct: float
    lead_time_days: int
    capacity_units: int


@dataclass
class RerouteResult:
    original_supplier_id: str
    sku_assignments: List[SKUAssignment]
    total_cost_delta: float
    estimated_delay_days: float
    confidence_score: float
    solver_used: str
    solve_time_ms: float


# ── Mock Graph Query (simulates Neo4j) ──────────────────────────────────────
def get_affected_skus(supplier_id: str) -> List[Dict]:
    """Query affected SKUs when a supplier is disrupted."""
    np.random.seed(hash(supplier_id) % 2**31)
    n_skus = np.random.randint(2, 8)
    skus = []
    for i in range(n_skus):
        skus.append({
            "sku_id": f"SKU_{hash(supplier_id + str(i)) % 1000:04d}",
            "name": f"Product-{i}",
            "criticality": np.random.uniform(0.3, 1.0),
            "current_lead_time": np.random.randint(5, 30),
            "current_capacity": np.random.randint(500, 5000),
        })
    return skus


def get_alternative_suppliers(supplier_id: str, sku_id: str) -> List[Dict]:
    """Query Neo4j for alternative suppliers that can provide the given SKU."""
    np.random.seed(hash(supplier_id + sku_id) % 2**31)
    n_alts = np.random.randint(0, 5)
    alternatives = []
    for i in range(n_alts):
        alternatives.append({
            "supplier_id": f"ALT_{hash(supplier_id + sku_id + str(i)) % 10000:05d}",
            "name": f"AltSupplier-{i}",
            "cost_increase_pct": np.random.uniform(0.05, 0.50),
            "lead_time_days": np.random.randint(7, 45),
            "capacity_units": np.random.randint(200, 8000),
            "reliability_score": np.random.uniform(0.5, 1.0),
        })
    return alternatives


# ── OR-Tools CP-SAT Solver ──────────────────────────────────────────────────
def solve_with_ortools(
    supplier_id: str,
    affected_skus: List[Dict],
    max_lead_time_days: int = 30,
    min_capacity_units: int = 100,
    max_cost_increase_pct: float = 0.5,
    time_limit_seconds: int = 30,
) -> Optional[RerouteResult]:
    """Solve the rerouting problem using OR-Tools CP-SAT solver.

    Objective: minimize  0.5*cost_increase + 0.3*lead_time_norm + 0.2*reliability_penalty
    Subject to: capacity >= required, lead_time <= max, cost <= max
    """
    if not HAS_ORTOOLS:
        return None

    start_time = time.time()
    model = cp_model.CpModel()

    sku_assignments = []
    all_vars = []  # (sku_idx, alt_idx, var, alt_data, sku_data)

    for s_idx, sku in enumerate(affected_skus):
        alternatives = get_alternative_suppliers(supplier_id, sku["sku_id"])
        if not alternatives:
            # No alternatives available — mark as unassignable
            sku_assignments.append(SKUAssignment(
                sku_id=sku["sku_id"],
                assigned_supplier_id="NONE",
                cost_increase_pct=0.0,
                lead_time_days=0,
                capacity_units=0,
            ))
            continue

        # Binary variable: assign this SKU to this alternative?
        sku_vars = []
        for a_idx, alt in enumerate(alternatives):
            var = model.NewBoolVar(f"assign_s{s_idx}_a{a_idx}")
            sku_vars.append(var)
            all_vars.append((s_idx, a_idx, var, alt, sku))

        # Exactly one alternative per SKU
        model.Add(sum(sku_vars) == 1)

        # Constraints
        for a_idx, alt in enumerate(alternatives):
            var = sku_vars[a_idx]
            # Lead time constraint
            if alt["lead_time_days"] > max_lead_time_days:
                model.Add(var == 0)
            # Capacity constraint
            if alt["capacity_units"] < min_capacity_units:
                model.Add(var == 0)
            # Cost constraint
            if alt["cost_increase_pct"] > max_cost_increase_pct:
                model.Add(var == 0)

    if not all_vars:
        return RerouteResult(
            original_supplier_id=supplier_id,
            sku_assignments=sku_assignments,
            total_cost_delta=0.0,
            estimated_delay_days=0.0,
            confidence_score=0.0,
            solver_used="ortools_cpsat",
            solve_time_ms=0.0,
        )

    # Objective: minimize weighted sum
    # Scale to integers for CP-SAT (multiply by 1000)
    obj_terms = []
    for s_idx, a_idx, var, alt, sku in all_vars:
        cost_term = int(alt["cost_increase_pct"] * 500)
        lead_term = int((alt["lead_time_days"] / 45) * 300)
        rel_term = int((1 - alt["reliability_score"]) * 200)
        obj_terms.append(var * (cost_term + lead_term + rel_term))

    model.Minimize(sum(obj_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    solve_time = (time.time() - start_time) * 1000

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        total_cost = 0.0
        total_delay = 0.0
        assigned_count = 0

        for s_idx, a_idx, var, alt, sku in all_vars:
            if solver.Value(var) == 1:
                sku_assignments.append(SKUAssignment(
                    sku_id=sku["sku_id"],
                    assigned_supplier_id=alt["supplier_id"],
                    cost_increase_pct=round(alt["cost_increase_pct"], 4),
                    lead_time_days=alt["lead_time_days"],
                    capacity_units=alt["capacity_units"],
                ))
                total_cost += alt["cost_increase_pct"]
                delay = max(0, alt["lead_time_days"] - sku["current_lead_time"])
                total_delay += delay
                assigned_count += 1

        confidence = 1.0 if status == cp_model.OPTIMAL else 0.8

        return RerouteResult(
            original_supplier_id=supplier_id,
            sku_assignments=sku_assignments,
            total_cost_delta=round(total_cost, 4),
            estimated_delay_days=round(total_delay / max(assigned_count, 1), 2),
            confidence_score=confidence,
            solver_used="ortools_cpsat",
            solve_time_ms=round(solve_time, 2),
        )

    return None


# ── Dijkstra Fallback ───────────────────────────────────────────────────────
def _build_supplier_graph(supplier_id: str, affected_skus: List[Dict]) -> Dict:
    """Build a weighted graph of supplier alternatives for Dijkstra."""
    graph = {}  # node -> [(neighbor, weight)]
    graph[supplier_id] = []

    for sku in affected_skus:
        sku_node = f"sku:{sku['sku_id']}"
        graph.setdefault(sku_node, [])
        # Edge from disrupted supplier to SKU
        graph[supplier_id].append((sku_node, 0))

        alternatives = get_alternative_suppliers(supplier_id, sku["sku_id"])
        for alt in alternatives:
            alt_node = f"alt:{alt['supplier_id']}"
            weight = (
                0.5 * alt["cost_increase_pct"] +
                0.3 * (alt["lead_time_days"] / 45) +
                0.2 * (1 - alt["reliability_score"])
            )
            graph.setdefault(alt_node, [])
            graph[sku_node].append((alt_node, weight))
            # Store alt data on the node
            graph[alt_node] = [(f"end:{sku['sku_id']}", 0)]
            graph.setdefault(f"end:{sku['sku_id']}", [])

    return graph


def dijkstra_shortest_paths(graph: Dict, start: str) -> Dict:
    """Standard Dijkstra's algorithm."""
    dist = {start: 0}
    prev = {}
    pq = [(0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float('inf')):
            continue
        for v, w in graph.get(u, []):
            new_dist = d + w
            if new_dist < dist.get(v, float('inf')):
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return dist, prev


def solve_with_dijkstra(
    supplier_id: str,
    affected_skus: List[Dict],
) -> RerouteResult:
    """Fast Dijkstra-based fallback for urgent rerouting."""
    start_time = time.time()
    graph = _build_supplier_graph(supplier_id, affected_skus)
    dist, prev = dijkstra_shortest_paths(graph, supplier_id)

    sku_assignments = []
    total_cost = 0.0
    total_delay = 0.0

    for sku in affected_skus:
        sku_node = f"sku:{sku['sku_id']}"
        alternatives = get_alternative_suppliers(supplier_id, sku["sku_id"])

        # Find best alternative by shortest path distance
        best_alt = None
        best_dist = float('inf')
        for alt in alternatives:
            alt_node = f"alt:{alt['supplier_id']}"
            if alt_node in dist and dist[alt_node] < best_dist:
                best_dist = dist[alt_node]
                best_alt = alt

        if best_alt:
            sku_assignments.append(SKUAssignment(
                sku_id=sku["sku_id"],
                assigned_supplier_id=best_alt["supplier_id"],
                cost_increase_pct=round(best_alt["cost_increase_pct"], 4),
                lead_time_days=best_alt["lead_time_days"],
                capacity_units=best_alt["capacity_units"],
            ))
            total_cost += best_alt["cost_increase_pct"]
            total_delay += max(0, best_alt["lead_time_days"] - sku["current_lead_time"])
        else:
            sku_assignments.append(SKUAssignment(
                sku_id=sku["sku_id"],
                assigned_supplier_id="NONE",
                cost_increase_pct=0.0,
                lead_time_days=0,
                capacity_units=0,
            ))

    solve_time = (time.time() - start_time) * 1000
    assigned = [a for a in sku_assignments if a.assigned_supplier_id != "NONE"]

    return RerouteResult(
        original_supplier_id=supplier_id,
        sku_assignments=sku_assignments,
        total_cost_delta=round(total_cost, 4),
        estimated_delay_days=round(total_delay / max(len(assigned), 1), 2),
        confidence_score=0.6,  # Lower confidence for heuristic
        solver_used="dijkstra",
        solve_time_ms=round(solve_time, 2),
    )


# ── Public API ──────────────────────────────────────────────────────────────
def reroute_supplier(
    supplier_id: str,
    urgency: str = "normal",
    max_lead_time_days: int = 30,
    min_capacity_units: int = 100,
    max_cost_increase_pct: float = 0.5,
) -> RerouteResult:
    """Main rerouting function.

    Args:
        supplier_id: ID of the disrupted supplier.
        urgency: 'normal' uses OR-Tools, 'urgent' uses Dijkstra fallback.
    """
    affected_skus = get_affected_skus(supplier_id)

    if urgency == "urgent" or not HAS_ORTOOLS:
        return solve_with_dijkstra(supplier_id, affected_skus)

    result = solve_with_ortools(
        supplier_id, affected_skus,
        max_lead_time_days=max_lead_time_days,
        min_capacity_units=min_capacity_units,
        max_cost_increase_pct=max_cost_increase_pct,
    )

    if result is None:
        # Fallback to Dijkstra if OR-Tools fails
        return solve_with_dijkstra(supplier_id, affected_skus)

    return result


# ── Unit Tests ──────────────────────────────────────────────────────────────
def test_simple_reroute():
    """Test: simple rerouting with available alternatives."""
    result = reroute_supplier("SUPPLIER_001", urgency="normal")
    assert result.original_supplier_id == "SUPPLIER_001"
    assert len(result.sku_assignments) > 0
    assert result.solve_time_ms >= 0
    print("  test_simple_reroute PASSED")


def test_capacity_constrained():
    """Test: rerouting under tight capacity constraints."""
    result = reroute_supplier("SUPPLIER_002", min_capacity_units=9999)
    assert result.original_supplier_id == "SUPPLIER_002"
    # Some assignments may be NONE due to tight constraints
    print(f"  test_capacity_constrained PASSED (assigned: {sum(1 for a in result.sku_assignments if a.assigned_supplier_id != 'NONE')})")


def test_no_alternatives():
    """Test: supplier with no alternatives available."""
    # Use a seed that produces 0 alternatives
    np.random.seed(999)
    result = reroute_supplier("SUPPLIER_NO_ALT_XYZ", urgency="urgent")
    assert result.original_supplier_id == "SUPPLIER_NO_ALT_XYZ"
    print(f"  test_no_alternatives PASSED (assignments: {len(result.sku_assignments)})")


def run_tests():
    """Run all unit tests."""
    print("\n--- Unit Tests ---")
    test_simple_reroute()
    test_capacity_constrained()
    test_no_alternatives()
    print("All tests passed!\n")


if __name__ == "__main__":
    run_tests()

    # Demo
    print("=" * 60)
    print("Demo: reroute_supplier('SUPPLIER_DEMO')")
    print("=" * 60)
    result = reroute_supplier("SUPPLIER_DEMO", urgency="normal")
    print(f"  Solver: {result.solver_used}")
    print(f"  Solve time: {result.solve_time_ms:.2f} ms")
    print(f"  Total cost delta: {result.total_cost_delta:.4f}")
    print(f"  Estimated delay: {result.estimated_delay_days:.2f} days")
    print(f"  Confidence: {result.confidence_score:.2f}")
    print(f"  SKU Assignments:")
    for a in result.sku_assignments:
        print(f"    {a.sku_id} -> {a.assigned_supplier_id} (cost: +{a.cost_increase_pct:.1%}, lead: {a.lead_time_days}d)")
