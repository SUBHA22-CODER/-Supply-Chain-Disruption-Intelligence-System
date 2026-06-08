// 1. Cascade Analysis: Find all SKUs affected if a specific tier-3 supplier fails (traversing DEPENDS_ON and SUPPLIES)
MATCH (s:Supplier {id: 'Supplier_45'})-[:DEPENDS_ON*0..]->(downstream:Supplier)-[:SUPPLIES]->(sku:SKU)
RETURN DISTINCT sku.name, sku.category;

// 2. Identify High-Risk Routes: Find suppliers using routes with high average delays
MATCH (s:Supplier)-[u:USES_ROUTE]->(r:Route)
WHERE u.avg_delay_days > 3
RETURN s.name, r.origin_country, r.dest_country, u.avg_delay_days
ORDER BY u.avg_delay_days DESC;

// 3. Bottleneck Suppliers: Find Tier-1 suppliers that have the highest number of dependent downstream suppliers
MATCH (t3:Supplier)-[:DEPENDS_ON*1..2]->(t1:Supplier {tier: 1})
RETURN t1.name, count(t3) AS dependent_count
ORDER BY dependent_count DESC LIMIT 5;

// 4. Vulnerable SKUs: Find SKUs supplied by suppliers with a risk score > 0.8
MATCH (s:Supplier)-[:SUPPLIES]->(sku:SKU)
WHERE s.risk_score > 0.8
RETURN sku.id, sku.name, s.name, s.risk_score;

// 5. Shortest path to a critical SKU: Find the shortest dependency path from any tier-3 supplier to a specific SKU
MATCH p=shortestPath((t3:Supplier {tier: 3})-[:DEPENDS_ON*1..2]->(t1:Supplier)-[:SUPPLIES]->(sku:SKU {id: 'SKU_10'}))
RETURN p;
