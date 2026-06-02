export default function StatCard({ title, value, icon, color = "blue", subtitle }) {
    const colors = {
        blue: "from-blue-500 to-blue-600",
        green: "from-green-500 to-green-600",
        yellow: "from-yellow-500 to-yellow-600",
        red: "from-red-500 to-red-600",
        purple: "from-purple-500 to-purple-600",
    };

    return (
        <div className={`bg-gradient-to-br ${colors[color]} rounded-2xl p-6 shadow-xl`}>
            <div className="flex items-center justify-between mb-3">
                <span className="text-white/80 text-sm font-medium">{title}</span>
                <div className="text-2xl">{icon}</div>
            </div>
            <div className="text-4xl font-bold text-white">{value}</div>
            {subtitle && (
                <div className="text-white/70 text-xs mt-2">{subtitle}</div>
            )}
        </div>
    );
}