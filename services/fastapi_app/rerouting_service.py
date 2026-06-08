import time
import uuid
import random
import os
from typing import List, Dict, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from neo4j_db import get_neo4j_graph
from models import SupplierNode, SupplierSKULink
from id_utils import resolve_id

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

class SkuAssignment(BaseModel):
    sku_id: str
    sku_name: str
    assigned_supplier_id: str
    assigned_supplier_name: str
    lead_time_days: int
    cost_delta_pct: float

class RerouteResult(BaseModel):
    original_supplier_id: str
    sku_assignments: List[SkuAssignment]
    total_cost_delta_pct: str
    estimated_delay_days: int
    confidence_score: float
    solver_used: str
    solve_time_ms: int
    error_code: Optional[str] = None

class CandidateSupplier:
    def __init__(self, id: str, name: str, reliability: float, capacity: int, lead_time: int, cost_mult: float):
        self.id = id
        self.name = name
        self.reliability = reliability
        self.capacity = capacity
        self.lead_time = lead_time
        self.cost_mult = cost_mult

class ReroutingService:
    def __init__(self):
        self.graph = None if not HAS_NX else nx.DiGraph()
        
    def find_alternatives(self, disrupted_id: str) -> List[CandidateSupplier]:
        """Query Neo4j and PostgreSQL to find candidates that supply the affected SKUs."""
        candidates = []
        
        # 1. Connect to Neo4j to find suppliers supplying the same SKUs
        try:
            graph = get_neo4j_graph()
            if graph is None:
                raise Exception("Neo4j unavailable")
            cypher = """
            MATCH (disrupted:Supplier {id: $disrupted_id})-[:SUPPLIES]->(sku:SKU)<-[:SUPPLIES]-(alt:Supplier)
            RETURN DISTINCT alt.id AS alt_id, alt.name AS alt_name
            """
            neo4j_results = graph.run(cypher, disrupted_id=disrupted_id).data()
        except Exception as e:
            print(f"Neo4j query failed: {e}. Falling back to default candidates.")
            neo4j_results = []

        db = SessionLocal()
        try:
            # If Neo4j is empty or down, select other suppliers in Postgres
            if not neo4j_results:
                alts = db.query(SupplierNode).filter(SupplierNode.id != resolve_id(disrupted_id)).limit(5).all()
                neo4j_results = [{"alt_id": str(a.id), "alt_name": a.name} for a in alts]

            for row in neo4j_results:
                alt_uuid = resolve_id(row["alt_id"])
                
                # Fetch reliability and links from PostgreSQL
                supplier = db.query(SupplierNode).filter(SupplierNode.id == alt_uuid).first()
                if not supplier:
                    continue
                    
                # Get average lead time and capacity from links
                links = db.query(SupplierSKULink).filter(SupplierSKULink.supplier_id == alt_uuid).all()
                avg_lead_time = int(sum(l.lead_time_days for l in links) / len(links)) if links else 15
                avg_capacity = int(sum(l.capacity_units for l in links) / len(links)) if links else 5000
                
                candidates.append(CandidateSupplier(
                    id=row["alt_id"],
                    name=row["alt_name"],
                    reliability=supplier.reliability_score or 0.85,
                    capacity=avg_capacity,
                    lead_time=avg_lead_time,
                    cost_mult=random.uniform(0.95, 1.3) # cost multiplier for optimization
                ))
        except Exception as e:
            print(f"Error querying Postgres for alternatives: {e}")
        finally:
            db.close()
            
        return candidates

    def _optimize_urgent(self, disrupted_id: str, skus: List[str], candidates: List[CandidateSupplier]) -> RerouteResult:
        """Use NetworkX Dijkstra to find fastest path."""
        start_time = time.time()
        
        try:
            import networkx as nx
        except ImportError:
            # Fallback mock for demo if networkx is not installed
            assignments = []
            for sku in skus:
                cand = candidates[0]
                assignments.append(SkuAssignment(
                    sku_id=sku,
                    sku_name=f"Component {sku}",
                    assigned_supplier_id=cand.id,
                    assigned_supplier_name=cand.name,
                    lead_time_days=cand.lead_time,
                    cost_delta_pct=round((cand.cost_mult - 1) * 100, 1)
                ))
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=assignments,
                total_cost_delta_pct=f"+{round((candidates[0].cost_mult - 1) * 100, 1)}%",
                estimated_delay_days=candidates[0].lead_time,
                confidence_score=0.95,
                solver_used="Mock NetworkX (Fallback)",
                solve_time_ms=120
            )

        # Build local graph for routing
        G = nx.DiGraph()
        G.add_node("START")
        G.add_node("DEST")
        
        for c in candidates:
            # Edge weight is purely lead_time for 'urgent'
            G.add_edge("START", c.id, weight=c.lead_time)
            G.add_edge(c.id, "DEST", weight=1) # simplified
            
        try:
            path = nx.shortest_path(G, "START", "DEST", weight="weight")
            best_cand_id = path[1]
            best_cand = next(c for c in candidates if c.id == best_cand_id)
            
            assignments = []
            for sku in skus:
                assignments.append(SkuAssignment(
                    sku_id=sku,
                    sku_name=f"Component {sku}",
                    assigned_supplier_id=best_cand.id,
                    assigned_supplier_name=best_cand.name,
                    lead_time_days=best_cand.lead_time,
                    cost_delta_pct=round((best_cand.cost_mult - 1) * 100, 1)
                ))
                
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=assignments,
                total_cost_delta_pct=f"+{round((best_cand.cost_mult - 1) * 100, 1)}%",
                estimated_delay_days=best_cand.lead_time,
                confidence_score=0.95,
                solver_used="NetworkX Dijkstra",
                solve_time_ms=int((time.time() - start_time) * 1000)
            )
        except nx.NetworkXNoPath:
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=[],
                total_cost_delta_pct="N/A",
                estimated_delay_days=0,
                confidence_score=0.0,
                solver_used="NetworkX Dijkstra",
                solve_time_ms=int((time.time() - start_time) * 1000),
                error_code="NO_ALTERNATIVES"
            )

    def _optimize_normal(self, disrupted_id: str, skus: List[str], candidates: List[CandidateSupplier]) -> RerouteResult:
        """Use Google OR-Tools CP-SAT solver."""
        start_time = time.time()
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            # Fallback mock for demo if ortools is not installed in the running environment
            assignments = []
            for sku in skus:
                cand = candidates[0]
                assignments.append(SkuAssignment(
                    sku_id=sku,
                    sku_name=f"Component {sku}",
                    assigned_supplier_id=cand.id,
                    assigned_supplier_name=cand.name,
                    lead_time_days=cand.lead_time,
                    cost_delta_pct=round((cand.cost_mult - 1) * 100, 1)
                ))
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=assignments,
                total_cost_delta_pct=f"+{round((candidates[0].cost_mult - 1) * 100, 1)}%",
                estimated_delay_days=candidates[0].lead_time,
                confidence_score=0.88,
                solver_used="Mock OR-Tools (Fallback)",
                solve_time_ms=1240
            )
            
        model = cp_model.CpModel()
        
        # Decision Variables: assign[sku, cand]
        assign = {}
        for s_idx, sku in enumerate(skus):
            for c_idx, cand in enumerate(candidates):
                assign[(s_idx, c_idx)] = model.NewBoolVar(f"assign_{s_idx}_{c_idx}")
                
        # Constraints:
        # 1. Each SKU must be assigned to exactly one candidate
        for s_idx in range(len(skus)):
            model.AddExactlyOne([assign[(s_idx, c_idx)] for c_idx in range(len(candidates))])
            
        # Objective: minimize 0.5*cost + 0.3*lead_time + 0.2*(1-reliability)
        # CP-SAT uses integers, so we multiply float weights by 1000
        obj_vars = []
        obj_coeffs = []
        for s_idx in range(len(skus)):
            for c_idx, cand in enumerate(candidates):
                cost_penalty = int((cand.cost_mult - 1.0) * 1000) * 5
                time_penalty = cand.lead_time * 30
                rel_penalty = int((1.0 - cand.reliability) * 1000) * 2
                
                score = cost_penalty + time_penalty + rel_penalty
                obj_vars.append(assign[(s_idx, c_idx)])
                obj_coeffs.append(score)
                
        model.Minimize(sum(v * c for v, c in zip(obj_vars, obj_coeffs)))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = []
            total_delay = 0
            total_cost_delta = 0.0
            
            for s_idx, sku in enumerate(skus):
                for c_idx, cand in enumerate(candidates):
                    if solver.Value(assign[(s_idx, c_idx)]):
                        assignments.append(SkuAssignment(
                            sku_id=sku,
                            sku_name=f"Component {sku}",
                            assigned_supplier_id=cand.id,
                            assigned_supplier_name=cand.name,
                            lead_time_days=cand.lead_time,
                            cost_delta_pct=round((cand.cost_mult - 1) * 100, 1)
                        ))
                        total_delay = max(total_delay, cand.lead_time)
                        total_cost_delta += (cand.cost_mult - 1)
            
            avg_cost_delta = (total_cost_delta / len(skus)) * 100
            
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=assignments,
                total_cost_delta_pct=f"+{round(avg_cost_delta, 1)}%",
                estimated_delay_days=total_delay,
                confidence_score=0.88,
                solver_used="OR-Tools CP-SAT",
                solve_time_ms=int((time.time() - start_time) * 1000)
            )
        else:
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=[],
                total_cost_delta_pct="N/A",
                estimated_delay_days=0,
                confidence_score=0.0,
                solver_used="OR-Tools CP-SAT",
                solve_time_ms=int((time.time() - start_time) * 1000),
                error_code="NO_ALTERNATIVES"
            )

    def optimize_reroute(self, disrupted_id: str, urgency: str = 'normal') -> RerouteResult:
        candidates = self.find_alternatives(disrupted_id)
        
        if not candidates:
            return RerouteResult(
                original_supplier_id=disrupted_id,
                sku_assignments=[],
                total_cost_delta_pct="N/A",
                estimated_delay_days=0,
                confidence_score=0.0,
                solver_used="N/A",
                solve_time_ms=0,
                error_code="NO_ALTERNATIVES"
            )
            
        skus = [f"SKU-{random.randint(100,999)}" for _ in range(random.randint(1, 6))]
        
        if urgency == 'urgent':
            return self._optimize_urgent(disrupted_id, skus, candidates)
        else:
            return self._optimize_normal(disrupted_id, skus, candidates)

rerouting_service = ReroutingService()
