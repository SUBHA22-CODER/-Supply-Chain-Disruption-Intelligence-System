import { useEffect, useState, useRef } from 'react';
import { Activity, AlertTriangle } from 'lucide-react';

interface ActionItem {
  id: string;
  timestamp: string;
  type: 'risk_alert' | 'agent_action';
  supplier_id: string;
  message: string;
  risk_score?: number;
}

interface ActionFeedProps {
  onNewAlert: (supplierId: string) => void;
}

const ActionFeed = ({ onNewAlert }: ActionFeedProps) => {
  const [actions, setActions] = useState<ActionItem[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket
    ws.current = new WebSocket('ws://localhost:8000/ws/alerts');

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;

        const newAction: ActionItem = {
          id: Math.random().toString(36).substring(7),
          timestamp: new Date().toLocaleTimeString(),
          type: data.type || 'risk_alert',
          supplier_id: data.supplier_id,
          message: data.message,
          risk_score: data.risk_score,
        };

        setActions((prev) => [newAction, ...prev].slice(0, 50));
        
        if (data.type === 'risk_alert' && data.supplier_id) {
          onNewAlert(data.supplier_id);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    // Keepalive ping
    const interval = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      ws.current?.close();
    };
  }, [onNewAlert]);

  return (
    <div className="glass-panel absolute left-6 bottom-6 w-80 max-h-96 rounded-xl overflow-hidden flex flex-col z-10">
      <div className="bg-background/80 backdrop-blur border-b border-border p-3 flex items-center justify-between sticky top-0 z-10">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" /> Live Action Feed
        </h3>
        <span className="flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {actions.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">Listening for events...</p>
        ) : (
          actions.map((action) => (
            <div key={action.id} className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-border text-sm animate-in slide-in-from-left-4 fade-in duration-300">
              <div className="flex items-start gap-2">
                {action.risk_score && action.risk_score > 0.7 ? (
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                ) : (
                  <Activity className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold">{action.supplier_id}</span>
                    <span className="text-[10px] text-muted-foreground">{action.timestamp}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{action.message}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ActionFeed;
