import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const COLORS = {
    car: '#3b82f6',
    motorcycle: '#f59e0b',
    bus: '#10b981',
    truck: '#ef4444',
};

const VEHICLE_ICONS = {
    car: '🚗',
    motorcycle: '🏍️',
    bus: '🚌',
    truck: '🚛',
};

export default function VehicleBreakdown({ lanes }) {
    // Aggregate breakdown from all lanes
    const totals = {};
    lanes.forEach(lane => {
        Object.entries(lane.breakdown || {}).forEach(([type, count]) => {
            totals[type] = (totals[type] || 0) + count;
        });
    });

    const data = Object.entries(totals).map(([name, value]) => ({
        name,
        value,
    }));

    const totalVehicles = data.reduce((sum, item) => sum + item.value, 0);

    return (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <div className="mb-4">
                <h3 className="text-white text-lg font-bold">Vehicle Types</h3>
                <p className="text-slate-400 text-xs">Live breakdown by type</p>
            </div>

            {totalVehicles === 0 ? (
                <div className="h-48 flex items-center justify-center text-slate-500">
                    No vehicles detected
                </div>
            ) : (
                <>
                    <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={50}
                                outerRadius={80}
                                paddingAngle={3}
                                dataKey="value"
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[entry.name] || '#888'} />
                                ))}
                            </Pie>
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#f1f5f9'
                                }}
                            />
                        </PieChart>
                    </ResponsiveContainer>

                    {/* Breakdown list */}
                    <div className="space-y-2 mt-2">
                        {data.map(({ name, value }) => (
                            <div key={name} className="flex items-center justify-between bg-slate-900 rounded-lg px-3 py-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg">{VEHICLE_ICONS[name] || '🚙'}</span>
                                    <span className="text-slate-300 text-sm capitalize">{name}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="text-white font-bold">{value}</div>
                                    <div className="text-xs text-slate-500">
                                        {((value / totalVehicles) * 100).toFixed(0)}%
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}