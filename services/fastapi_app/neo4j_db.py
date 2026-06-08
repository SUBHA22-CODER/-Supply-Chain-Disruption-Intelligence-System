import os

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

HAS_PY2NEO = False
try:
    from py2neo import Graph
    HAS_PY2NEO = True
except ImportError:
    pass

def get_neo4j_graph():
    """Connect to Neo4j graph database. Returns None if py2neo is not installed or connection fails."""
    if not HAS_PY2NEO:
        print("py2neo not installed. Neo4j graph queries will be skipped.")
        return None
    try:
        return Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        print(f"Neo4j connection failed: {e}")
        return None
