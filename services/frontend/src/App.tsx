import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import MetricsBar from './components/MetricsBar';
import MapChart from './components/MapChart';
import SupplierPanel from './components/SupplierPanel';
import ActionFeed from './components/ActionFeed';
import CopilotWidget from './components/CopilotWidget';
import ScenarioSimulator from './components/ScenarioSimulator';
import DriftMonitor from './components/DriftMonitor';

// Demo admin token (should match backend config)
const DEMO_TOKEN = btoa(JSON.stringify({ sub: "admin", exp: new Date(Date.now() + 86400000).toISOString(), secret: "admin123" }));

const fetchMetrics = async () => {
  const res = await fetch('http://localhost:8000/api/metrics', {
    headers: { Authorization: `Bearer ${DEMO_TOKEN}` }
  });
  if (!res.ok) throw new Error('Failed to fetch metrics');
  return res.json();
};

const fetchSuppliers = async () => {
  const res = await fetch('http://localhost:8000/api/suppliers', {
    headers: { Authorization: `Bearer ${DEMO_TOKEN}` }
  });
  if (!res.ok) throw new Error('Failed to fetch suppliers');
  return res.json();
};

function App() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return document.documentElement.classList.contains('dark') || 
             window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return true;
  });

  const [selectedSupplierId, setSelectedSupplierId] = useState<string | undefined>();
  const [activeAlerts, setActiveAlerts] = useState<string[]>([]);
  
  // New features UI toggles
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);
  const [isMLOpsOpen, setIsMLOpsOpen] = useState(false);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 30000,
  });

  const { data: suppliers = [], refetch: refetchSuppliers } = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
    refetchInterval: 30000,
  });

  const handleNewAlert = (supplierId: string) => {
    setActiveAlerts(prev => [...new Set([...prev, supplierId])]);
    refetchSuppliers(); // Refresh data to get new risk score
    
    // Auto-remove pulse after 10 seconds
    setTimeout(() => {
      setActiveAlerts(prev => prev.filter(id => id !== supplierId));
    }, 10000);
  };

  return (
    <div className="w-screen h-screen overflow-hidden bg-slate-50 dark:bg-slate-950 flex flex-col font-sans transition-colors duration-500 relative">
      {/* Premium ambient gradient blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/20 blur-[120px] pointer-events-none" />
      
      <MetricsBar 
        metrics={metrics} 
        isDark={isDark} 
        toggleDarkMode={() => setIsDark(!isDark)}
        onToggleSimulator={() => {
          setIsSimulatorOpen(!isSimulatorOpen);
          setIsMLOpsOpen(false);
        }}
        onToggleMLOps={() => {
          setIsMLOpsOpen(!isMLOpsOpen);
          setIsSimulatorOpen(false);
        }}
        isSimulatorOpen={isSimulatorOpen}
        isMLOpsOpen={isMLOpsOpen}
      />
      
      <main className="flex-1 relative w-full h-full">
        {/* Interactive Map with Grid */}
        <div className="absolute inset-0 map-grid-pattern transition-opacity duration-500">
          <MapChart 
            suppliers={suppliers}
            selectedSupplierId={selectedSupplierId}
            onSelectSupplier={(s) => setSelectedSupplierId(s.id)}
            activeAlerts={activeAlerts}
          />
        </div>

        {/* Live Action Feed */}
        <ActionFeed onNewAlert={handleNewAlert} />

        {/* Scenario Simulator Side Panel */}
        {isSimulatorOpen && (
          <ScenarioSimulator 
            token={DEMO_TOKEN} 
            suppliers={suppliers}
            onClose={() => setIsSimulatorOpen(false)} 
          />
        )}

        {/* MLOps Drift Diagnostics modal */}
        {isMLOpsOpen && (
          <DriftMonitor 
            token={DEMO_TOKEN} 
            onClose={() => setIsMLOpsOpen(false)} 
          />
        )}

        {/* Supplier Detail Panel */}
        {selectedSupplierId && (
          <SupplierPanel 
            supplierId={selectedSupplierId} 
            onClose={() => setSelectedSupplierId(undefined)}
            token={DEMO_TOKEN}
          />
        )}

        {/* GenAI Copilot Widget */}
        <CopilotWidget token={DEMO_TOKEN} />
      </main>
    </div>
  );
}

export default App;
