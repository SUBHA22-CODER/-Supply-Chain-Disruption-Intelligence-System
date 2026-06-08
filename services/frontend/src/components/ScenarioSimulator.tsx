import React, { useState } from 'react';

interface ScenarioSimulatorProps {
  token: string;
  suppliers: any[];
  onClose: () => void;
}

export default function ScenarioSimulator({ token, suppliers, onClose }: ScenarioSimulatorProps) {
  const [scenarioType, setScenarioType] = useState('supplier_failure');
  const [targetId, setTargetId] = useState('');
  const [multiplier, setMultiplier] = useState(2.0);
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Set default target supplier on load
  React.useEffect(() => {
    if (suppliers.length > 0 && !targetId) {
      setTargetId(suppliers[0].id);
    }
  }, [suppliers, targetId]);

  const handleSimulate = async () => {
    setIsLoading(true);
    setResult(null);

    try {
      const res = await fetch('http://localhost:8000/api/simulate/scenario', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          scenario_type: scenarioType,
          target_id: targetId,
          multiplier: scenarioType === 'demand_surge' ? multiplier : 1.0
        })
      });

      if (!res.ok) throw new Error('Simulation failed');
      const data = await res.json();
      setResult(data);
    } catch (err) {
      alert('Simulation failed. Please check backend log.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed top-20 left-6 bottom-6 w-96 bg-slate-900/95 border border-slate-700/50 rounded-2xl shadow-2xl backdrop-blur-xl flex flex-col z-40 overflow-hidden animate-slide-in">
      {/* Header */}
      <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
        <span className="font-semibold text-slate-100 text-sm">Scenario Simulator</span>
        <button 
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 text-xs transition-colors"
        >
          Close
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Scenario Config Form */}
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Scenario Type</label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="supplier_failure">Supplier Outage / Failure</option>
              <option value="port_closure">Port / Route Closure</option>
              <option value="demand_surge">Global Demand Shock</option>
            </select>
          </div>

          {scenarioType === 'supplier_failure' && (
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Target Supplier</label>
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {suppliers.map(s => (
                  <option key={s.id} value={s.id}>{s.name} (Risk: {Math.round(s.risk_score * 100)}%)</option>
                ))}
              </select>
            </div>
          )}

          {scenarioType === 'port_closure' && (
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Select Port/Route Route</label>
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="Route_Ocean_East">Ocean Route East (Port of Shanghai)</option>
                <option value="Route_Ocean_West">Ocean Route West (Port of Rotterdam)</option>
                <option value="Route_Air_Main">Primary Air Cargo Route</option>
              </select>
            </div>
          )}

          {scenarioType === 'demand_surge' && (
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Demand Multiplier</label>
              <input 
                type="number"
                step="0.5"
                min="1.0"
                max="5.0"
                value={multiplier}
                onChange={(e) => setMultiplier(parseFloat(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          <button
            onClick={handleSimulate}
            disabled={isLoading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-2 text-xs font-semibold transition-colors flex items-center justify-center space-x-2"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Evaluating Impact...</span>
              </>
            ) : (
              <span>Run Scenario Simulation</span>
            )}
          </button>
        </div>

        {/* Results Block */}
        {result && (
          <div className="mt-4 border-t border-slate-800 pt-4 space-y-3">
            <span className="text-xs font-bold text-slate-200 block">Simulation Results</span>
            
            {scenarioType === 'supplier_failure' && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                    <span className="block text-[9px] uppercase tracking-wider text-slate-500">Cost Impact</span>
                    <span className={`text-sm font-bold block ${result.reroute_feasible ? 'text-amber-500' : 'text-slate-400'}`}>
                      {result.cost_delta}
                    </span>
                  </div>
                  <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                    <span className="block text-[9px] uppercase tracking-wider text-slate-500">Delay Impact</span>
                    <span className="text-sm font-bold text-emerald-500 block">
                      +{result.estimated_delay_days} Days
                    </span>
                  </div>
                </div>

                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <span className="block text-[9px] uppercase tracking-wider text-slate-500 mb-1">Alternative Assignments</span>
                  <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1 text-[10px]">
                    {result.assignments.map((asg: any, i: number) => (
                      <div key={i} className="flex justify-between border-b border-slate-900 pb-1">
                        <span className="text-slate-400">{asg.sku_name}</span>
                        <span className="text-slate-200 font-medium">{asg.assigned_supplier_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {scenarioType === 'port_closure' && (
              <div className="space-y-3">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">System Risk Lift:</span>
                    <span className="text-rose-500 font-bold">{result.system_risk_delta}</span>
                  </div>
                  <span className="block text-[9px] uppercase tracking-wider text-slate-500 mb-1">Simulated Lead Times</span>
                  <div className="space-y-1.5 text-[10px]">
                    {result.simulated_updates.map((upd: any, i: number) => (
                      <div key={i} className="flex justify-between border-b border-slate-900 pb-1">
                        <span className="text-slate-400">SKU {upd.sku_id.slice(0, 8)}...</span>
                        <span className="text-rose-500">{upd.original_lead_time}d → {upd.simulated_lead_time}d</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {scenarioType === 'demand_surge' && (
              <div className="space-y-3">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Capacity Bottlenecks:</span>
                    <span className="text-rose-500 font-bold">{result.bottlenecks_detected} Detected</span>
                  </div>
                  <span className="block text-[9px] uppercase tracking-wider text-slate-500 mb-1">Bottleneck Details</span>
                  <div className="space-y-1.5 text-[10px]">
                    {result.bottleneck_details.map((bn: any, i: number) => (
                      <div key={i} className="flex justify-between border-b border-slate-900 pb-1">
                        <span className="text-slate-400">SKU {bn.sku_id.slice(0,8)}</span>
                        <span className="text-rose-400">{bn.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
