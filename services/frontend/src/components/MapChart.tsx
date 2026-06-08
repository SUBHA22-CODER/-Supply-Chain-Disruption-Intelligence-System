import React, { useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

const countryCoords: Record<string, [number, number]> = {
  "India": [78.9629, 20.5937],
  "China": [104.1954, 35.8617],
  "USA": [-95.7129, 37.0902],
  "Germany": [10.4515, 51.1657],
  "Brazil": [-51.9253, -14.2350]
};

interface Supplier {
  id: string;
  name: string;
  country: string;
  tier: number;
  risk_score: number;
  trend: string;
}

interface MapChartProps {
  suppliers: Supplier[];
  onSelectSupplier: (supplier: Supplier) => void;
  selectedSupplierId?: string;
  activeAlerts: string[];
}

const MapChart: React.FC<MapChartProps> = ({ suppliers, onSelectSupplier, selectedSupplierId, activeAlerts }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  
  const markers = useMemo(() => {
    return suppliers.map(s => {
      const baseCoord = countryCoords[s.country] || [0, 0];
      const hash = s.id.split('_')[1] ? parseInt(s.id.split('_')[1]) : 0;
      const jitterX = (hash % 10 - 5) * 1.5;
      const jitterY = ((hash * 7) % 10 - 5) * 1.5;
      return {
        ...s,
        coordinates: [baseCoord[0] + jitterX, baseCoord[1] + jitterY] as [number, number]
      };
    });
  }, [suppliers]);

  useEffect(() => {
    if (!svgRef.current) return;
    
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = 800;
    const height = 600;
    
    // Set up projection and path generator
    const projection = d3.geoMercator()
      .scale(130)
      .translate([width / 2, height / 1.5]);
      
    const path = d3.geoPath().projection(projection);

    const g = svg.append("g");

    // Enable zooming
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
      
    svg.call(zoom);

    // Load topology and render map
    d3.json(geoUrl).then(() => {
      
      // Since world-atlas is topojson, we need to convert to geojson
      // Actually it's easier to fetch a raw geojson for this pure D3 impl
      // Fallback: draw basic circles if topojson is not available
      d3.json("https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson").then((data: any) => {
        g.selectAll("path")
          .data(data.features)
          .join("path")
          .attr("d", path as any)
          .attr("fill", "currentColor")
          .attr("stroke", "currentColor")
          .attr("stroke-width", 0.5)
          .attr("stroke-opacity", 0.2)
          .attr("class", "text-slate-300 dark:text-slate-800 transition-colors duration-500 drop-shadow-md");

        // Render markers
        markers.forEach(marker => {
          const [x, y] = projection(marker.coordinates) || [0, 0];
          const isSelected = selectedSupplierId === marker.id;
          const isAlerting = activeAlerts.includes(marker.id);
          
          let color = "#10b981"; // green
          if (marker.risk_score > 0.7) color = "#ef4444"; // red
          else if (marker.risk_score > 0.4) color = "#f59e0b"; // amber

          const markerGroup = g.append("g")
            .attr("transform", `translate(${x},${y})`)
            .attr("cursor", "pointer")
            .on("click", () => onSelectSupplier(marker));

          if (isAlerting) {
            markerGroup.append("circle")
              .attr("r", 8)
              .attr("fill", color)
              .attr("class", "animate-pulse-ring")
              .attr("opacity", 0.6);
          }

          markerGroup.append("circle")
            .attr("r", isSelected ? 6 : 4)
            .attr("fill", color)
            .attr("stroke", "#fff")
            .attr("stroke-width", isSelected ? 2 : 1)
            .attr("class", "transition-all duration-300");

          if (isSelected) {
            markerGroup.append("text")
              .attr("text-anchor", "middle")
              .attr("y", -12)
              .attr("class", "text-xs font-semibold fill-slate-800 dark:fill-slate-200 pointer-events-none")
              .text(marker.name);
          }
        });
      });
    });

  }, [markers, selectedSupplierId, activeAlerts, onSelectSupplier]);

  return (
    <div className="w-full h-full relative overflow-hidden flex items-center justify-center">
      <svg 
        ref={svgRef} 
        viewBox="0 0 800 600" 
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full max-w-5xl"
      />
    </div>
  );
};

export default MapChart;
