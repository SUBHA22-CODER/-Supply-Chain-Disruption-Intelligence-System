import React from 'react';
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Info } from 'lucide-react';

interface ForecastData {
  day: string;
  low: number;
  mid: number;
  high: number;
}

interface ForecastChartProps {
  data: ForecastData[];
}

const ForecastChart: React.FC<ForecastChartProps> = ({ data }) => {
  const isElevated = data.some(d => d.mid > 60);

  return (
    <div className="bg-slate-900/40 p-4 rounded-2xl border border-white/5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-slate-400">
          <h3 className="text-xs font-bold uppercase tracking-wider">3-Day Forecast</h3>
          <div className="group relative">
            <Info className="w-3.5 h-3.5 cursor-help" />
            <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-48 p-2 bg-slate-800 text-[10px] text-slate-200 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 text-center shadow-xl border border-slate-700">
              Shows predicted risk score. The shaded area represents the 10th-90th percentile confidence bounds.
            </div>
          </div>
        </div>
        {isElevated && (
          <span className="text-[10px] font-bold bg-red-500/10 text-red-400 px-2 py-1 rounded-full border border-red-500/20">
            Elevated risk predicted
          </span>
        )}
      </div>

      <div className="h-32 w-full mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -25 }}>
            <defs>
              <linearGradient id="colorConfidence" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.05} vertical={false} />
            <XAxis dataKey="day" stroke="currentColor" fontSize={10} opacity={0.4} axisLine={false} tickLine={false} />
            <YAxis stroke="currentColor" fontSize={10} opacity={0.4} domain={[0, 100]} axisLine={false} tickLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.95)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '0.75rem', color: '#fff', padding: '8px' }}
              itemStyle={{ fontSize: '11px', fontWeight: 'bold' }}
              labelStyle={{ fontSize: '10px', color: '#94a3b8', marginBottom: '4px' }}
            />
            {/* Area for confidence band (low to high) */}
            <Area type="monotone" dataKey="high" stroke="none" fill="url(#colorConfidence)" />
            <Area type="monotone" dataKey="low" stroke="none" fill="hsl(var(--background))" />
            
            <ReferenceLine y={60} stroke="#ef4444" strokeDasharray="3 3" opacity={0.5} />
            
            <Line type="monotone" dataKey="mid" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4, strokeWidth: 2, fill: '#0f172a' }} activeDot={{ r: 6 }} name="Predicted Risk" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ForecastChart;
