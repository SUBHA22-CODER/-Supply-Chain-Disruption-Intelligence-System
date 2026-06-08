import os
import random
import uuid
import json
import csv
from py2neo import Graph, Node, Relationship

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

def build_graph():
    print("Connecting to Neo4j...")
    graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Clear existing
    graph.delete_all()
    
    shared_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data", "shared_ids.json"
    )
    
    if not os.path.exists(shared_file):
        print("Error: shared_ids.json does not exist. Run generate_shared_ids.py first.")
        return

    with open(shared_file, "r") as f:
        shared_data = json.load(f)
        
    print("Generating Neo4j graph from shared_ids.json...")
    
    # Load suppliers
    suppliers = shared_data["suppliers"]
    supplier_ids = [s["id"] for s in suppliers]
    
    tier1, tier2, tier3 = [], [], []
    for i, s_info in enumerate(suppliers):
        s_id = s_info["id"]
        if i < 10:
            tier = 1
            tier1.append(s_id)
        elif i < 30:
            tier = 2
            tier2.append(s_id)
        else:
            tier = 3
            tier3.append(s_id)
            
        node = Node("Supplier", id=s_id, name=s_info["name"], country="Global", tier=tier, risk_score=random.uniform(0, 1))
        graph.create(node)

    # Generate SKUs
    skus = shared_data["skus"]
    sku_ids = [sku["id"] for sku in skus]
    for sku_info in skus:
        node = Node("SKU", id=sku_info["id"], name=sku_info["name"], category="General")
        graph.create(node)

    # Generate Routes
    routes = [f"Route_{i}" for i in range(30)]
    for i, route in enumerate(routes):
        node = Node("Route", id=route, origin_country="A", dest_country="B", transport_mode="Ocean")
        graph.create(node)

    # SUPPLIES Relationship: Suppliers -> SKUs
    print("Creating SUPPLIES relationships...")
    for supp in supplier_ids:
        for _ in range(random.randint(1, 5)):
            sku = random.choice(sku_ids)
            query = f"""
            MATCH (s:Supplier {{id: '{supp}'}}), (p:SKU {{id: '{sku}'}})
            MERGE (s)-[:SUPPLIES {{lead_time: {random.randint(10, 30)}, capacity: {random.randint(100, 1000)}}}]->(p)
            """
            graph.run(query)

    # DEPENDS_ON Relationship
    print("Creating DEPENDS_ON relationships...")
    for t3 in tier3:
        t2 = random.choice(tier2)
        query = f"MATCH (s3:Supplier {{id: '{t3}'}}), (s2:Supplier {{id: '{t2}'}}) MERGE (s3)-[:DEPENDS_ON {{dependency_type: 'critical'}}]->(s2)"
        graph.run(query)

    for t2 in tier2:
        t1 = random.choice(tier1)
        query = f"MATCH (s2:Supplier {{id: '{t2}'}}), (s1:Supplier {{id: '{t1}'}}) MERGE (s2)-[:DEPENDS_ON {{dependency_type: 'raw_material'}}]->(s1)"
        graph.run(query)

    # USES_ROUTE Relationship
    print("Creating USES_ROUTE relationships...")
    for supp in supplier_ids:
        route = random.choice(routes)
        query = f"MATCH (s:Supplier {{id: '{supp}'}}), (r:Route {{id: '{route}'}}) MERGE (s)-[:USES_ROUTE {{freight_cost: {random.uniform(100, 1000)}, avg_delay_days: {random.randint(0, 5)}}}]->(r)"
        graph.run(query)

    # Cascade Analysis Query (If Supplier X fails, which SKUs are at risk?)
    test_supplier = random.choice(tier3)
    print(f"Running cascade analysis for {test_supplier}...")
    cascade_query = f"""
    MATCH (s:Supplier {{id: '{test_supplier}'}})-[:DEPENDS_ON*0..]->(downstream:Supplier)-[:SUPPLIES]->(sku:SKU)
    RETURN DISTINCT sku.id AS affected_sku
    """
    results = graph.run(cascade_query).data()
    print(f"Affected SKUs: {[r['affected_sku'] for r in results]}")

    # Export Edge List for GNN
    print("Exporting edge list for GNN training...")
    edges_query = "MATCH (a)-[r]->(b) RETURN labels(a)[0] AS a_type, a.id AS a_id, type(r) AS rel_type, labels(b)[0] AS b_type, b.id AS b_id"
    edges = graph.run(edges_query).data()
    
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "processed", "edge_list.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["a_type", "a_id", "rel_type", "b_type", "b_id"])
        writer.writeheader()
        writer.writerows(edges)
    print("Graph built and edge list exported.")

if __name__ == "__main__":
    build_graph()
