import { Car, Bus, Truck, Bike } from 'lucide-react';
import Header from './components/Header';
import StatCard from './components/StatCard';
import SignalLight from './components/SignalLight';
import LiveChart from './components/LiveChart';
import ManualOverride from './components/ManualOverride';
import { useTrafficData } from './hooks/useTrafficData';

function App() {
  const intersectionId = 'intersection_1';
  const { data, history, isOnline, refetch } = useTrafficData(intersectionId);

  const vehicleCount = data?.vehicle_count ?? 0;
  const signalState = data?.signal_state ?? 'GREEN';
  const lastUpdated = data?.last_updated
    ? new Date(data.last_updated).toLocaleTimeString()
    : 'Never';

  return (
    <div className="min-h-screen bg-slate-900">
      <Header isOnline={isOnline} />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Status Banner */}
        {!isOnline && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-6">
            <p className="text-red-200">
              ⚠️ Cannot connect to backend at http://localhost:8000
            </p>
          </div>
        )}

        {/* Top Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Total Vehicles"
            value={vehicleCount}
            icon="🚗"
            color="blue"
            subtitle={`Updated: ${lastUpdated}`}
          />
          <StatCard
            title="Signal State"
            value={signalState}
            icon="🚦"
            color={signalState === 'GREEN' ? 'green' : signalState === 'YELLOW' ? 'yellow' : 'red'}
          />
          <StatCard
            title="Intersection"
            value="#1"
            icon="📍"
            color="purple"
            subtitle={intersectionId}
          />
          <StatCard
            title="System Status"
            value={isOnline ? "ONLINE" : "OFFLINE"}
            icon={isOnline ? "✅" : "❌"}
            color={isOnline ? "green" : "red"}
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Chart - takes 2 columns */}
          <div className="lg:col-span-2">
            <LiveChart data={history} />
          </div>

          {/* Signal Light */}
          <div>
            <SignalLight state={signalState} />
          </div>
        </div>

        {/* Bottom Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent History Table */}
          <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <h3 className="text-white text-lg font-bold mb-4">Recent Activity</h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {history.slice(-10).reverse().map((item, i) => (
                <div key={i} className="flex items-center justify-between bg-slate-900 rounded-lg px-4 py-2">
                  <span className="text-slate-400 text-sm">
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="text-white font-medium">
                    {item.count} vehicles
                  </span>
                  <span className={`text-xs px-2 py-1 rounded ${item.signal === 'GREEN' ? 'bg-green-900 text-green-300' :
                      item.signal === 'YELLOW' ? 'bg-yellow-900 text-yellow-300' :
                        'bg-red-900 text-red-300'
                    }`}>
                    {item.signal}
                  </span>
                </div>
              ))}
              {history.length === 0 && (
                <p className="text-slate-500 text-center py-8">No data yet. Start the detector!</p>
              )}
            </div>
          </div>

          {/* Manual Override Panel */}
          <ManualOverride intersectionId={intersectionId} onUpdate={refetch} />
        </div>

        {/* Footer */}
        <footer className="mt-8 text-center text-slate-500 text-sm">
          <p>SMART_ROUTE © 2025 | Team Path Finders | SIH 2025</p>
        </footer>
      </main>
    </div>
  );
}

export default App;