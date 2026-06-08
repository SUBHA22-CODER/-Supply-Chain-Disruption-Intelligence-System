import React from 'react';
import { Activity, AlertTriangle, Route, ShieldAlert, Moon, Sun, Play, Cpu } from 'lucide-react';

interface Metrics {
  suppliers_monitored: number;
  alerts_triggered_today: number;
  avg_response_time_ms: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
}

interface MetricsBarProps {
  metrics: Metrics | null;
  toggleDarkMode: () => void;
  isDark: boolean;
  onToggleSimulator: () => void;
  onToggleMLOps: () => void;
  isSimulatorOpen: boolean;
  isMLOpsOpen: boolean;
}

const MetricsBar: React.FC<MetricsBarProps> = ({ 
  metrics, 
  toggleDarkMode, 
  isDark,
  onToggleSimulator,
  onToggleMLOps,
  isSimulatorOpen,
  isMLOpsOpen
}) => {
  return (
    <div className="glass w-full px-8 py-5 flex items-center justify-between sticky top-0 z-20 border-b border-white/10 dark:border-white/5">
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-primary/10 dark:bg-primary/20 backdrop-blur-md border border-primary/20">
          <ShieldAlert className="w-6 h-6 text-primary drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
        </div>
        <div>
          <h1 className="text-2xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-slate-900 to-slate-500 dark:from-white dark:to-slate-400">
            Supply Chain Disruption Intelligence
          </h1>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mt-0.5">Live Global Monitoring System</p>
        </div>
      </div>

      <div className="flex items-center gap-8">
        <MetricItem 
          icon={<Activity className="w-5 h-5 text-emerald-500 drop-shadow-[0_0_5px_rgba(16,185,129,0.4)]" />}
          label="Monitored Nodes"
          value={metrics?.suppliers_monitored || 0}
        />
        <div className="w-px h-10 bg-slate-200 dark:bg-slate-800 shadow-[1px_0_0_0_rgba(255,255,255,0.1)]"></div>
        <MetricItem 
          icon={<AlertTriangle className="w-5 h-5 text-red-500 drop-shadow-[0_0_5px_rgba(239,68,68,0.4)]" />}
          label="High Risk Nodes"
          value={metrics?.high_risk_count || 0}
        />
        <div className="w-px h-10 bg-slate-200 dark:bg-slate-800 shadow-[1px_0_0_0_rgba(255,255,255,0.1)]"></div>
        <MetricItem 
          icon={<Route className="w-5 h-5 text-amber-500 drop-shadow-[0_0_5px_rgba(245,158,11,0.4)]" />}
          label="Active Reroutes"
          value={metrics?.alerts_triggered_today || 0}
        />
        <div className="w-px h-10 bg-slate-200 dark:bg-slate-800 shadow-[1px_0_0_0_rgba(255,255,255,0.1)]"></div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Simulator Toggle */}
          <button
            onClick={onToggleSimulator}
            className={`p-3 rounded-xl transition-all duration-300 border flex items-center gap-1.5 text-xs font-semibold whitespace-nowrap ${
              isSimulatorOpen 
                ? 'bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20' 
                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border-white/20 dark:border-white/5'
            }`}
            title="Toggle Scenario Simulator"
          >
            <Play className="w-4 h-4 flex-shrink-0" />
            <span>Simulator</span>
          </button>

          {/* Model Health Toggle */}
          <button
            onClick={onToggleMLOps}
            className={`p-3 rounded-xl transition-all duration-300 border flex items-center gap-1.5 text-xs font-semibold whitespace-nowrap ${
              isMLOpsOpen 
                ? 'bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20' 
                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border-white/20 dark:border-white/5'
            }`}
            title="Toggle Model Health Monitor"
          >
            <Cpu className="w-4 h-4 flex-shrink-0" />
            <span>Model Health</span>
          </button>

          {/* Dark Mode */}
          <button 
            onClick={toggleDarkMode}
            className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all duration-300 border border-white/20 dark:border-white/5"
            aria-label="Toggle dark mode"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.6)]" /> : <Moon className="w-4 h-4 text-slate-600" />}
          </button>
        </div>
      </div>
    </div>
  );
};

const MetricItem = ({ icon, label, value }: { icon: React.ReactNode, label: string, value: number }) => (
  <div className="flex items-center gap-4 group cursor-default">
    <div className="p-3 rounded-xl bg-white/50 dark:bg-slate-900/50 shadow-sm border border-slate-200/50 dark:border-slate-700/50 group-hover:scale-110 transition-transform duration-300">
      {icon}
    </div>
    <div className="flex flex-col justify-center">
      <p className="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-widest">{label}</p>
      <p className="text-2xl font-black text-slate-800 dark:text-slate-100 leading-none mt-1 group-hover:text-primary transition-colors duration-300">{value}</p>
    </div>
  </div>
);

export default MetricsBar;
