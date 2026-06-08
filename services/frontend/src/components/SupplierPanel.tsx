import { useQuery } from '@tanstack/react-query';
import { X, AlertCircle, RefreshCw } from 'lucide-react';
import ForecastChart from './ForecastChart';
import ShapWaterfall from './ShapWaterfall';
import RerouteButton from './RerouteButton';

interface SupplierPanelProps {
  supplierId: string;
  onClose: () => void;
  token: string;
}

const fetchRiskDetails = async (supplierId: string, token: string) => {
  const res = await fetch(`http://localhost:8000/api/suppliers/${supplierId}/risk`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch risk details');
  return res.json();
};



const SupplierPanel = ({ supplierId, onClose, token }: SupplierPanelProps) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['supplierRisk', supplierId],
    queryFn: () => fetchRiskDetails(supplierId, token),
    refetchInterval: 30000,
  });



  if (isLoading) return (
    <div className="glass-panel absolute right-6 top-24 w-96 h-[calc(100vh-120px)] rounded-xl p-6 flex items-center justify-center animate-in slide-in-from-right-8">
      <RefreshCw className="w-8 h-8 animate-spin text-primary" />
    </div>
  );

  if (error || !data) return null;

  // Prepare Forecast Data
  const forecastData = data.tft_forecast || [
    { day: 'T+1', mid: data.forecast_quantiles?.['50th']?.[0] || 0.1, low: data.forecast_quantiles?.['10th']?.[0] || 0.05, high: data.forecast_quantiles?.['90th']?.[0] || 0.15 },
    { day: 'T+2', mid: data.forecast_quantiles?.['50th']?.[1] || 0.15, low: data.forecast_quantiles?.['10th']?.[1] || 0.1, high: data.forecast_quantiles?.['90th']?.[1] || 0.2 },
    { day: 'T+3', mid: data.forecast_quantiles?.['50th']?.[2] || 0.2, low: data.forecast_quantiles?.['10th']?.[2] || 0.15, high: data.forecast_quantiles?.['90th']?.[2] || 0.3 },
  ];

  // Prepare SHAP Data
  const shapData = data.shap_reasons || [
    { feature: 'GNN Risk', value: data.gnn_risk_score, direction: 'positive' },
    { feature: 'Geo Risk', value: data.geo_risk_score, direction: 'positive' },
    { feature: 'TFT Forecast', value: data.tft_3day_forecast, direction: 'positive' },
  ];

  const getScoreColor = (score: number) => {
    if (score > 0.7) return 'text-red-500';
    if (score > 0.4) return 'text-amber-500';
    return 'text-emerald-500';
  };

  return (
    <div className="glass-panel absolute right-6 top-28 bottom-6 w-[480px] rounded-2xl flex flex-col animate-in slide-in-from-right-8 z-20 border border-white/20 dark:border-white/10 shadow-2xl shadow-primary/10 overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-white/10 dark:border-white/5 bg-background/80 backdrop-blur-xl shrink-0 z-10">
        <div>
          <h2 className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-500 dark:from-white dark:to-slate-400">{supplierId}</h2>
          <p className="text-[11px] text-muted-foreground font-bold uppercase tracking-widest mt-1">Risk Profile Breakdown</p>
        </div>
        <button onClick={onClose} className="p-2.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-red-500 transition-all duration-300">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-6 space-y-6 overflow-y-auto flex-1 custom-scrollbar">
        {/* Risk Score Gauge */}
        <div className="relative overflow-hidden flex items-center justify-between bg-white/40 dark:bg-slate-900/40 p-5 rounded-2xl border border-white/20 dark:border-white/5 shadow-inner">
          <div className="absolute -right-4 -top-4 w-24 h-24 bg-primary/10 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <p className="text-sm font-semibold text-muted-foreground mb-1 uppercase tracking-wider">Overall Risk</p>
            <div className="flex items-end gap-2 mt-1">
              <span className={`text-4xl font-black drop-shadow-md ${getScoreColor(data.risk_score)}`}>
                {(data.risk_score * 100).toFixed(1)}
              </span>
              <span className="text-lg font-bold text-muted-foreground mb-1">/ 100</span>
            </div>
          </div>
          <div className="text-right relative z-10 border-l border-slate-200 dark:border-slate-800 pl-5">
            <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">Confidence</p>
            <p className="text-xl font-bold text-slate-800 dark:text-slate-200">{(data.confidence * 100).toFixed(1)}%</p>
          </div>
        </div>

        {/* Top 3 Reasons */}
        <div>
          <h3 className="text-xs font-bold mb-3 flex items-center gap-2 uppercase tracking-wider text-slate-700 dark:text-slate-300">
            <AlertCircle className="w-4 h-4 text-primary" /> Key Risk Drivers
          </h3>
          <ul className="space-y-2">
            {data.top_3_reasons.map((r: string, i: number) => (
              <li key={i} className="text-sm font-medium flex items-center gap-3 bg-white/60 dark:bg-slate-900/40 p-3 rounded-xl border border-slate-200/50 dark:border-slate-800/50 hover:border-primary/30 transition-colors shadow-sm">
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary font-bold text-[10px] shrink-0">{i + 1}</span>
                <span className="text-slate-700 dark:text-slate-300 leading-tight">{r}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Forecast Chart */}
        <ForecastChart data={forecastData} />

        {/* Component Risk Chart (SHAP) */}
        <ShapWaterfall 
          baselineRisk={0.35} 
          totalRisk={data.risk_score || data.fusion_score || 0.5} 
          reasons={shapData} 
        />
      </div>

      <div className="p-5 border-t border-white/10 dark:border-white/5 bg-background/80 backdrop-blur-xl shrink-0 z-10">
        <RerouteButton supplierId={supplierId} token={token} />
      </div>
    </div>
  );
};

export default SupplierPanel;
