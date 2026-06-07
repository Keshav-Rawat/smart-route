import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function LaneComparisonChart({ lanes }) {
    const data = lanes.map(lane => ({
        name: lane.name,
        Current: lane.current,
        Total: lane.cumulative,
    }));

    return (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-white text-lg font-bold">Lane Comparison</h3>
                    <p className="text-slate-400 text-xs">Current vs Total vehicles per lane</p>
                </div>
            </div>

            <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                            color: '#f1f5f9'
                        }}
                    />
                    <Legend wrapperStyle={{ color: '#94a3b8' }} />
                    <Bar dataKey="Current" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="Total" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}