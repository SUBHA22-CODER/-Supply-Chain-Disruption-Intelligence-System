import React, { useEffect, useState } from 'react';

interface ShapReason {
  feature: string;
  value: number;
  direction: 'positive' | 'negative';
}

interface ShapWaterfallProps {
  baselineRisk: number;
  totalRisk: number;
  reasons: ShapReason[];
}

const ShapWaterfall: React.FC<ShapWaterfallProps> = ({ baselineRisk, totalRisk, reasons }) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Trigger animation after slight delay
    const timer = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(timer);
  }, []);

  // Calculate cumulative values to position bars correctly
  let currentVal = baselineRisk;
  const bars = reasons.slice(0, 5).map((reason) => {
    const start = currentVal;
    currentVal += (reason.direction === 'positive' ? reason.value : -reason.value);
    
    return {
      ...reason,
      start,
      end: currentVal,
      isPositive: reason.direction === 'positive',
    };
  });

  // Calculate overall range to map values to percentages (0-100)
  const minVal = 0; // Risk is bounded 0-1
  const maxVal = 1;

  const toPercent = (val: number) => ((val - minVal) / (maxVal - minVal)) * 100;

  return (
    <div className="bg-slate-900/40 p-4 rounded-2xl border border-white/5">
      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">SHAP Risk Explanations</h3>
      
      <div className="space-y-3 font-mono text-xs">
        {/* Baseline Bar */}
        <div className="flex items-center gap-3">
          <div className="w-32 truncate text-slate-500 font-sans">Baseline Risk</div>
          <div className="flex-1 relative h-6 bg-slate-800/50 rounded overflow-hidden">
            <div 
              className="absolute top-0 bottom-0 left-0 bg-slate-500 transition-all duration-700 ease-out"
              style={{ width: mounted ? `${toPercent(baselineRisk)}%` : '0%' }}
            />
          </div>
          <div className="w-12 text-right text-slate-400">{baselineRisk.toFixed(2)}</div>
        </div>

        {/* SHAP Reason Bars */}
        {bars.map((bar, i) => {
          const width = Math.abs(toPercent(bar.end) - toPercent(bar.start));
          const left = toPercent(Math.min(bar.start, bar.end));
          
          return (
            <div key={i} className="flex items-center gap-3 group">
              <div className="w-32 truncate text-slate-300 font-sans" title={bar.feature}>
                {bar.feature}
              </div>
              <div className="flex-1 relative h-6 bg-slate-800/20 rounded overflow-hidden">
                {/* Reference line at start of bar */}
                <div 
                  className="absolute top-0 bottom-0 w-px bg-slate-700 z-10 transition-all duration-700"
                  style={{ left: `${toPercent(bar.start)}%` }}
                />
                
                {/* The actual colored bar */}
                <div 
                  className={`absolute top-0 bottom-0 transition-all duration-700 ease-out ${
                    bar.isPositive ? 'bg-red-500/80' : 'bg-emerald-500/80'
                  }`}
                  style={{ 
                    left: `${left}%`, 
                    width: mounted ? `${width}%` : '0%' 
                  }}
                />
              </div>
              <div className={`w-12 text-right font-bold ${bar.isPositive ? 'text-red-400' : 'text-emerald-400'}`}>
                {bar.isPositive ? '+' : '-'}{Math.abs(bar.value).toFixed(2)}
              </div>
            </div>
          );
        })}

        <div className="border-t border-slate-700/50 pt-3 mt-3 flex items-center gap-3">
          <div className="w-32 font-bold font-sans text-slate-200">Total Risk Score</div>
          <div className="flex-1 relative h-6 bg-slate-800/50 rounded overflow-hidden">
             <div 
              className={`absolute top-0 bottom-0 left-0 transition-all duration-700 ease-out ${
                totalRisk > 0.6 ? 'bg-red-500' : totalRisk > 0.4 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{ width: mounted ? `${toPercent(totalRisk)}%` : '0%' }}
            />
          </div>
          <div className="w-12 text-right font-bold text-white text-sm">{totalRisk.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
};

export default ShapWaterfall;
