import { useState, useEffect, useRef } from 'react';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { Activity, Wifi, WifiOff, RefreshCw, Zap, TrendingDown, TrendingUp, Clock } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const INTERSECTION_ID = 'intersection_1';

/* ── Simulation results from the last Python run ─────────────── */
const SIM_RESULTS = {
  fixed:    { avg_queue: 35.69, max_queue: 69,  throughput: 2401 },
  adaptive: { avg_queue: 31.9,  max_queue: 66,  throughput: 2457 },
};

/* ── Custom Tooltip ───────────────────────────────────────────── */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(13,18,32,0.95)',
      border: '1px solid rgba(0,212,255,0.2)',
      borderRadius: 10,
      padding: '10px 14px',
      backdropFilter: 'blur(12px)',
      fontSize: 12,
    }}>
      <p style={{ color: '#94a3b8', marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: <span style={{ color: '#f1f5f9' }}>{p.value}</span>
        </p>
      ))}
    </div>
  );
};

/* ── Traffic Light ────────────────────────────────────────────── */
function TrafficLight({ state }) {
  const lights = [
    { color: '#ef4444', glow: 'rgba(239,68,68,0.6)',   active: state === 'RED'    },
    { color: '#f59e0b', glow: 'rgba(245,158,11,0.6)',  active: state === 'YELLOW' },
    { color: '#10b981', glow: 'rgba(16,185,129,0.6)',  active: state === 'GREEN'  },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      <div style={{
        background: '#060a12',
        borderRadius: 20,
        padding: '20px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        border: '2px solid rgba(255,255,255,0.08)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
      }}>
        {lights.map((l, i) => (
          <div key={i} style={{
            width: 56, height: 56,
            borderRadius: '50%',
            background: l.active ? l.color : 'rgba(255,255,255,0.05)',
            boxShadow: l.active ? `0 0 20px ${l.glow}, 0 0 40px ${l.glow}` : 'none',
            transition: 'all 0.4s ease',
          }} />
        ))}
      </div>
      <span style={{
        fontSize: 13, fontWeight: 700, letterSpacing: '0.1em',
        color: state === 'RED' ? '#ef4444' : state === 'YELLOW' ? '#f59e0b' : '#10b981',
        textShadow: `0 0 12px currentColor`,
      }}>{state}</span>
    </div>
  );
}

/* ── Intersection Map ─────────────────────────────────────────── */
function IntersectionMap({ queueNS = 0, queueEW = 0, signal = 'GREEN' }) {
  const maxQ = 80;
  const nsW = Math.min(100, (queueNS / maxQ) * 100);
  const ewW = Math.min(100, (queueEW / maxQ) * 100);

  const sigColor = signal === 'GREEN' ? '#10b981' : signal === 'YELLOW' ? '#f59e0b' : '#ef4444';

  return (
    <div style={{ position: 'relative', width: '100%', aspectRatio: '1/1', maxWidth: 280, margin: '0 auto' }}>
      {/* Road NS */}
      <div style={{
        position: 'absolute', left: '42%', top: 0, width: '16%', height: '100%',
        background: '#1a2035', borderRadius: 4,
      }}>
        {/* Lane markings */}
        {[15,35,55,75].map(y => (
          <div key={y} style={{
            position: 'absolute', left: '48%', top: `${y}%`,
            width: 3, height: '8%', background: 'rgba(255,255,255,0.12)', borderRadius: 2,
          }}/>
        ))}
        {/* NS queue bar */}
        <div style={{
          position: 'absolute', bottom: '52%', left: '10%', right: '10%',
          height: `${nsW * 0.45}%`, maxHeight: '44%',
          background: `linear-gradient(to bottom, ${sigColor}60, ${sigColor}20)`,
          borderRadius: '4px 4px 0 0', transition: 'height 0.6s ease',
          border: `1px solid ${sigColor}40`,
        }}/>
      </div>

      {/* Road EW */}
      <div style={{
        position: 'absolute', top: '42%', left: 0, height: '16%', width: '100%',
        background: '#1a2035', borderRadius: 4,
      }}>
        {[15,35,55,75].map(x => (
          <div key={x} style={{
            position: 'absolute', top: '48%', left: `${x}%`,
            width: '8%', height: 3, background: 'rgba(255,255,255,0.12)', borderRadius: 2,
          }}/>
        ))}
        {/* EW queue bar */}
        <div style={{
          position: 'absolute', right: '52%', top: '10%', bottom: '10%',
          width: `${ewW * 0.44}%`, maxWidth: '44%',
          background: `linear-gradient(to right, #00d4ff60, #00d4ff20)`,
          borderRadius: '4px 0 0 4px', transition: 'width 0.6s ease',
          border: '1px solid rgba(0,212,255,0.3)',
        }}/>
      </div>

      {/* Center box */}
      <div style={{
        position: 'absolute', left: '42%', top: '42%', width: '16%', height: '16%',
        background: '#1e2d47', border: `2px solid ${sigColor}`,
        boxShadow: `0 0 20px ${sigColor}60`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'border-color 0.4s, box-shadow 0.4s',
        borderRadius: 2,
      }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: sigColor, boxShadow: `0 0 8px ${sigColor}` }}/>
      </div>

      {/* Labels */}
      {[
        { text: 'N', style: { top: 4, left: '46%' } },
        { text: 'S', style: { bottom: 4, left: '46%' } },
        { text: 'W', style: { left: 4, top: '46%' } },
        { text: 'E', style: { right: 4, top: '46%' } },
      ].map(({ text, style }) => (
        <span key={text} style={{
          position: 'absolute', fontSize: 11, fontWeight: 700,
          color: '#64748b', fontFamily: 'var(--font-mono)', ...style,
        }}>{text}</span>
      ))}

      {/* Queue labels */}
      <div style={{ position: 'absolute', top: '20%', left: '60%', fontSize: 11, color: '#94a3b8' }}>
        NS: <strong style={{ color: '#f1f5f9' }}>{queueNS}</strong>
      </div>
      <div style={{ position: 'absolute', top: '60%', left: '10%', fontSize: 11, color: '#94a3b8' }}>
        EW: <strong style={{ color: '#f1f5f9' }}>{queueEW}</strong>
      </div>
    </div>
  );
}

/* ── Stat Card ────────────────────────────────────────────────── */
function StatCard({ label, value, sub, accent = '#00d4ff', icon: Icon, trend }) {
  return (
    <div className="card" style={{
      padding: '20px 22px',
      borderLeft: `3px solid ${accent}`,
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: -20, right: -20,
        width: 80, height: 80, borderRadius: '50%',
        background: `radial-gradient(circle, ${accent}15, transparent 70%)`,
      }}/>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        {Icon && <Icon size={16} style={{ color: accent }} />}
      </div>
      <div style={{ fontSize: 32, fontWeight: 800, lineHeight: 1, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>{sub}</div>}
      {trend !== undefined && (
        <div style={{ fontSize: 12, marginTop: 6, color: trend < 0 ? '#10b981' : '#ef4444', display: 'flex', alignItems: 'center', gap: 4 }}>
          {trend < 0 ? <TrendingDown size={12}/> : <TrendingUp size={12}/>}
          {Math.abs(trend).toFixed(1)}% vs fixed
        </div>
      )}
    </div>
  );
}

/* ── KPI Comparison Card ──────────────────────────────────────── */
function KPICard({ label, fixed, adaptive, unit = '', lowerBetter = true }) {
  const pct = ((adaptive - fixed) / fixed) * 100;
  const improved = lowerBetter ? pct < 0 : pct > 0;
  return (
    <div className="card" style={{ padding: '18px 20px', textAlign: 'center' }}>
      <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</p>
      <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <p style={{ fontSize: 10, color: '#ff6b6b', marginBottom: 4 }}>Fixed</p>
          <p style={{ fontSize: 22, fontWeight: 800, color: '#ff6b6b', fontVariantNumeric: 'tabular-nums' }}>{fixed}{unit}</p>
        </div>
        <div style={{ fontSize: 20, color: 'var(--text-muted)' }}>→</div>
        <div>
          <p style={{ fontSize: 10, color: '#00d4ff', marginBottom: 4 }}>Adaptive</p>
          <p style={{ fontSize: 22, fontWeight: 800, color: '#00d4ff', fontVariantNumeric: 'tabular-nums' }}>{adaptive}{unit}</p>
        </div>
      </div>
      <div style={{
        display: 'inline-block',
        padding: '4px 12px',
        borderRadius: 20,
        background: improved ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
        color: improved ? '#10b981' : '#ef4444',
        fontSize: 12, fontWeight: 700,
      }}>
        {pct < 0 ? '▼' : '▲'} {Math.abs(pct).toFixed(1)}% {improved ? '✓' : '✗'}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════════════════════ */
export default function App() {
  const [data, setData]       = useState(null);
  const [history, setHistory] = useState([]);
  const [isOnline, setIsOnline] = useState(false);
  const [tick, setTick]       = useState(0);

  /* Live fetch */
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [r1, r2] = await Promise.all([
          fetch(`${API_URL}/traffic/${INTERSECTION_ID}`),
          fetch(`${API_URL}/traffic/${INTERSECTION_ID}/history`),
        ]);
        const d1 = await r1.json();
        const d2 = await r2.json();
        setData(d1);
        setHistory(d2.history || []);
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    };
    fetchData();
    const iv = setInterval(() => { fetchData(); setTick(t => t + 1); }, 2000);
    return () => clearInterval(iv);
  }, []);

  /* Derived */
  const vehicleCount = data?.vehicle_count ?? 0;
  const signalState  = data?.signal_state  ?? 'GREEN';
  const lanes = data?.lanes
    ? Object.entries(data.lanes).map(([name, info]) => ({
        name: name.toUpperCase(), current: info.current || 0,
        cumulative: info.cumulative || 0, direction: info.direction || '—',
      }))
    : [];

  const qNS = lanes.filter(l => ['N','S','NORTH_IN','SOUTH_IN'].some(d => l.name.includes(d)))
    .reduce((s, l) => s + l.current, 0);
  const qEW = lanes.filter(l => ['E','W','EAST_IN','WEST_IN'].some(d => l.name.includes(d)))
    .reduce((s, l) => s + l.current, 0);

  const chartData = history.slice(-24).map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    count: h.count,
    signal: h.signal === 'GREEN' ? 3 : h.signal === 'YELLOW' ? 2 : 1,
  }));

  const laneData = lanes.map(l => ({ name: l.name, current: l.current, total: l.cumulative }));

  const sigColor = signalState === 'GREEN' ? '#10b981' : signalState === 'YELLOW' ? '#f59e0b' : '#ef4444';
  const pctAdaptiveThroughput = (((SIM_RESULTS.adaptive.throughput - SIM_RESULTS.fixed.throughput) / SIM_RESULTS.fixed.throughput) * 100).toFixed(1);
  const pctAdaptiveQueue     = (((SIM_RESULTS.adaptive.avg_queue  - SIM_RESULTS.fixed.avg_queue)  / SIM_RESULTS.fixed.avg_queue)  * 100).toFixed(1);

  return (
    <div style={{ minHeight: '100vh' }}>

      {/* ── Header ────────────────────────────────────────────── */}
      <header style={{
        borderBottom: '1px solid var(--border)',
        background: 'rgba(7,11,20,0.85)',
        backdropFilter: 'blur(20px)',
        position: 'sticky', top: 0, zIndex: 100,
        padding: '0 32px',
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: 'linear-gradient(135deg, #00d4ff, #3b82f6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, boxShadow: '0 0 20px rgba(0,212,255,0.3)',
            }}>🚦</div>
            <div>
              <h1 style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(90deg,#00d4ff,#3b82f6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                SmartRoute
              </h1>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>ADAPTIVE TRAFFIC CONTROL</p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            {/* Live clock */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              <Clock size={13} />
              {new Date().toLocaleTimeString()}
            </div>
            {/* Connection badge */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 7, padding: '6px 14px',
              borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: isOnline ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
              border: `1px solid ${isOnline ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
              color: isOnline ? '#10b981' : '#ef4444',
            }}>
              {isOnline ? <Wifi size={13}/> : <WifiOff size={13}/>}
              {isOnline ? 'Live' : 'Offline'}
              {isOnline && <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', animation: 'pulse 1.5s infinite' }}/>}
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1400, margin: '0 auto', padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 28 }}>

        {/* ── Offline banner ──────────────────────────────────── */}
        {!isOnline && (
          <div style={{
            padding: '14px 20px', borderRadius: 'var(--radius-md)',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.25)',
            color: '#fca5a5', fontSize: 13,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <WifiOff size={16}/> Backend offline — showing simulation results only. Start the API with <code style={{ fontFamily: 'var(--font-mono)', background: 'rgba(0,0,0,0.3)', padding: '2px 8px', borderRadius: 4 }}>uvicorn main:app --reload</code>
          </div>
        )}

        {/* ── Row 1: Stat cards ───────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16 }}>
          <StatCard label="Live Vehicles"    value={vehicleCount}                   icon={Activity} accent="#00d4ff" sub="at intersection now" />
          <StatCard label="Adaptive Throughput" value={SIM_RESULTS.adaptive.throughput} icon={Zap}      accent="#3b82f6" sub="vehicles/hr (sim)" trend={parseFloat(pctAdaptiveThroughput)} />
          <StatCard label="Avg Queue Reduced" value={`${Math.abs(pctAdaptiveQueue)}%`} icon={TrendingDown} accent="#10b981" sub="vs fixed-time baseline" />
          <StatCard label="Signal State"     value={signalState}                    icon={Activity} accent={sigColor} sub="current phase" />
        </div>

        {/* ── Row 2: Intersection + Live chart + Traffic light ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 200px', gap: 16 }}>

          {/* Intersection Map */}
          <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Intersection</h3>
            <IntersectionMap queueNS={qNS || 20} queueEW={qEW || 8} signal={signalState} />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
              Queue bars scale to max 80 vehicles
            </div>
          </div>

          {/* Live Traffic Chart */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Live Traffic Flow</h3>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>2s interval</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="gCyan" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#00d4ff" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" name="Vehicles" stroke="#00d4ff" fill="url(#gCyan)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Traffic Light */}
          <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Signal</h3>
            <TrafficLight state={signalState} />
            <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
              Webster algorithm<br/>adjusts phase duration
            </div>
          </div>
        </div>

        {/* ── Row 3: Simulation KPI Comparison ────────────────── */}
        <div className="card" style={{ padding: '22px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
            <div style={{ width: 4, height: 20, borderRadius: 2, background: 'linear-gradient(to bottom, #00d4ff, #3b82f6)' }}/>
            <h2 style={{ fontSize: 14, fontWeight: 700 }}>Webster Adaptive vs Fixed-Time — Simulation Results</h2>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>1-hour SUMO simulation · 3,600 steps</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
            <KPICard label="Average Queue"  fixed={SIM_RESULTS.fixed.avg_queue}    adaptive={SIM_RESULTS.adaptive.avg_queue}    unit=" veh" lowerBetter={true}  />
            <KPICard label="Peak Queue"     fixed={SIM_RESULTS.fixed.max_queue}    adaptive={SIM_RESULTS.adaptive.max_queue}    unit=" veh" lowerBetter={true}  />
            <KPICard label="Throughput"     fixed={SIM_RESULTS.fixed.throughput}   adaptive={SIM_RESULTS.adaptive.throughput}   unit=" veh" lowerBetter={false} />
          </div>
        </div>

        {/* ── Row 4: Lane breakdown + Webster explanation ─────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>

          {/* Lane bar chart */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 18 }}>Lane Traffic (Live)</h3>
            {laneData.length > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={laneData} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="current" name="Now"   fill="#00d4ff" radius={[4,4,0,0]} />
                  <Bar dataKey="total"   name="Total" fill="#3b82f6" radius={[4,4,0,0]} opacity={0.6} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8, color: 'var(--text-muted)' }}>
                <Activity size={24} style={{ opacity: 0.4 }} />
                <p style={{ fontSize: 13 }}>No lane data — backend offline</p>
                <p style={{ fontSize: 11 }}>Simulation ran 4 lanes: north_in, south_in, east_in, west_in</p>
              </div>
            )}
          </div>

          {/* Webster explanation */}
          <div className="card" style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>How It Works</h3>
            {[
              { step: '01', color: '#00d4ff', title: 'Sense', desc: 'TraCI polls halting vehicle count on each approach lane every 30 seconds.' },
              { step: '02', color: '#3b82f6', title: 'Compute', desc: 'Webster\'s formula splits green time proportional to queue ratios (min 10s, max 60s).' },
              { step: '03', color: '#8b5cf6', title: 'Adapt', desc: 'New phase durations are pushed live to the traffic light via setProgramLogic().' },
              { step: '04', color: '#10b981', title: 'Result', desc: '10.6% lower average queue, 2.3% more throughput vs fixed 42s cycle.' },
            ].map(({ step, color, title, desc }) => (
              <div key={step} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div style={{
                  minWidth: 32, height: 32, borderRadius: 8,
                  background: `${color}20`, border: `1px solid ${color}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 800, color, fontFamily: 'var(--font-mono)',
                }}>{step}</div>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 700, marginBottom: 3 }}>{title}</p>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Footer ──────────────────────────────────────────── */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            SmartRoute · Webster Adaptive Signal Control · SUMO 1.20.0
          </p>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {isOnline ? `⬤ Live · last update ${new Date(data?.last_updated || Date.now()).toLocaleTimeString()}` : '⬤ Simulation mode'}
          </p>
        </div>

      </main>

      <style>{`
        .card {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-card);
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .card:hover {
          border-color: var(--border-bright);
          box-shadow: var(--shadow-card), 0 0 0 1px rgba(0,212,255,0.05);
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(0.8); }
        }
        @media (max-width: 1024px) {
          main { padding: 20px 16px; }
          div[style*="grid-template-columns: repeat(4"] { grid-template-columns: repeat(2,1fr) !important; }
          div[style*="grid-template-columns: 280px"] { grid-template-columns: 1fr !important; }
          div[style*="grid-template-columns: 1fr 380px"] { grid-template-columns: 1fr !important; }
          div[style*="grid-template-columns: repeat(3"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}