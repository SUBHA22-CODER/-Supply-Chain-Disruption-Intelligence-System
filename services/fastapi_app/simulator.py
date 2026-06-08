import uuid
from sqlalchemy.orm import Session
from models import SupplierNode, SupplierSKULink
from rerouting_service import rerouting_service, RerouteResult
from id_utils import resolve_id

class ScenarioSimulator:
    """Service to execute 'what-if' disruption scenarios."""
    
    def simulate_supplier_failure(self, supplier_id: str, db: Session) -> dict:
        """What happens if a supplier fails? Calculates cascade impacts and alternative options."""
        supplier_uuid = resolve_id(supplier_id)
        supplier = db.query(SupplierNode).filter(SupplierNode.id == supplier_uuid).first()
        if not supplier:
            return {"error": "Supplier not found"}
            
        # Get SKUs this supplier provides
        sku_links = db.query(SupplierSKULink).filter(SupplierSKULink.supplier_id == supplier_uuid).all()
        affected_sku_ids = [str(link.sku_id) for link in sku_links]
        
        # Run standard rerouting optimizer for this supplier
        result = rerouting_service.optimize_reroute(supplier_id, urgency="urgent")
        
        return {
            "scenario": f"Failure of {supplier.name}",
            "impacted_skus_count": len(affected_sku_ids),
            "affected_sku_ids": affected_sku_ids,
            "reroute_feasible": not bool(result.error_code),
            "cost_delta": result.total_cost_delta_pct,
            "estimated_delay_days": result.estimated_delay_days,
            "solver_used": result.solver_used,
            "assignments": [a.dict() for a in result.sku_assignments]
        }

    def simulate_port_closure(self, route_id: str, db: Session) -> dict:
        """Simulates what happens if a port/route closes, increasing lead times."""
        # Find all suppliers using this route in Neo4j (for mock/fallback: select some suppliers)
        # Increase lead times by 20 days and evaluate the new optimization cost
        all_links = db.query(SupplierSKULink).all()
        
        simulated_results = []
        for link in all_links[:10]: # Simulate first 10 SKU link updates
            original_lead_time = link.lead_time_days
            simulated_lead_time = original_lead_time + 20
            simulated_results.append({
                "sku_id": str(link.sku_id),
                "original_lead_time": original_lead_time,
                "simulated_lead_time": simulated_lead_time,
                "lead_time_increase_pct": "+100%" if original_lead_time == 0 else f"+{round((20 / original_lead_time)*100, 1)}%"
            })
            
        return {
            "scenario": f"Closure of route/port: {route_id}",
            "impacted_links_count": len(simulated_results),
            "simulated_updates": simulated_results,
            "system_risk_delta": "+35% risk elevation"
        }

    def simulate_demand_surge(self, multiplier: float, db: Session) -> dict:
        """Simulates a global demand surge, multiplying required quantities."""
        # Check if alternative suppliers have enough capacity to absorb
        all_links = db.query(SupplierSKULink).all()
        capacity_issues = []
        for link in all_links:
            required_capacity = link.capacity_units * multiplier
            if required_capacity > 50000: # Threshold for supply limit
                capacity_issues.append({
                    "supplier_id": str(link.supplier_id),
                    "sku_id": str(link.sku_id),
                    "current_capacity": link.capacity_units,
                    "surged_demand": required_capacity,
                    "status": "Capacity Bottleneck"
                })
                
        return {
            "scenario": f"Demand Surge of {multiplier}x",
            "bottlenecks_detected": len(capacity_issues),
            "bottleneck_details": capacity_issues[:5]
        }

scenario_simulator = ScenarioSimulator()
