import React from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, ArrowRight, Clock, DollarSign, Activity } from 'lucide-react';

interface SkuAssignment {
  sku_id: string;
  sku_name: string;
  assigned_supplier_name: string;
  lead_time_days: number;
  cost_delta_pct: number;
}

interface RerouteResult {
  total_cost_delta_pct: string;
  estimated_delay_days: number;
  confidence_score: number;
  solver_used: string;
  solve_time_ms: number;
  sku_assignments: SkuAssignment[];
}

interface RerouteResultModalProps {
  result: RerouteResult;
  onClose: () => void;
  onApply: () => void;
}

const RerouteResultModal: React.FC<RerouteResultModalProps> = ({ result, onClose, onApply }) => {
  return createPortal(
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-800 bg-slate-800/50 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-6 h-6 text-emerald-500" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Reroute Plan Found</h2>
            <p className="text-sm text-slate-400">Optimization complete. Alternative supply lines identified.</p>
          </div>
        </div>

        {/* Summary Metrics */}
        <div className="grid grid-cols-3 divide-x divide-slate-800 border-b border-slate-800">
          <div className="p-6">
            <div className="flex items-center gap-2 text-slate-400 mb-2">
              <DollarSign className="w-4 h-4" /> <span className="text-xs font-bold uppercase tracking-wider">Cost Impact</span>
            </div>
            <p className="text-2xl font-bold text-amber-500">{result.total_cost_delta_pct}</p>
          </div>
          <div className="p-6">
            <div className="flex items-center gap-2 text-slate-400 mb-2">
              <Clock className="w-4 h-4" /> <span className="text-xs font-bold uppercase tracking-wider">Est. Delay</span>
            </div>
            <p className="text-2xl font-bold text-amber-500">+{result.estimated_delay_days} days</p>
          </div>
          <div className="p-6">
            <div className="flex items-center gap-2 text-slate-400 mb-2">
              <Activity className="w-4 h-4" /> <span className="text-xs font-bold uppercase tracking-wider">Confidence</span>
            </div>
            <p className="text-2xl font-bold text-emerald-500">{(result.confidence_score * 100).toFixed(1)}%</p>
          </div>
        </div>

        {/* Table */}
        <div className="p-6 overflow-y-auto max-h-96 custom-scrollbar">
          <h3 className="text-sm font-bold text-slate-300 mb-4">SKU Reassignments</h3>
          <div className="border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 font-semibold">SKU</th>
                  <th className="px-4 py-3 font-semibold">New Supplier</th>
                  <th className="px-4 py-3 font-semibold">Lead Time</th>
                  <th className="px-4 py-3 font-semibold">Cost Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300">
                {result.sku_assignments.map((sku, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-bold">{sku.sku_id}</div>
                      <div className="text-xs text-slate-500">{sku.sku_name}</div>
                    </td>
                    <td className="px-4 py-3 flex items-center gap-2">
                      <ArrowRight className="w-4 h-4 text-slate-600" />
                      <span className="font-semibold">{sku.assigned_supplier_name}</span>
                    </td>
                    <td className="px-4 py-3">{sku.lead_time_days} days</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        sku.cost_delta_pct > 25 ? 'bg-red-500/10 text-red-400' :
                        sku.cost_delta_pct > 10 ? 'bg-amber-500/10 text-amber-400' :
                        'bg-emerald-500/10 text-emerald-400'
                      }`}>
                        {sku.cost_delta_pct > 0 ? '+' : ''}{sku.cost_delta_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-800 bg-slate-900 flex items-center justify-between">
          <div className="text-xs text-slate-500 font-mono">
            Optimized via {result.solver_used} ({result.solve_time_ms}ms)
          </div>
          <div className="flex gap-3">
            <button 
              onClick={onClose}
              className="px-6 py-2.5 rounded-xl font-bold text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button 
              onClick={onApply}
              className="px-6 py-2.5 rounded-xl font-bold text-white bg-primary hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
            >
              Apply Reroute
            </button>
          </div>
        </div>

      </div>
    </div>,
    document.body
  );
};

export default RerouteResultModal;
