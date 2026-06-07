import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Car } from 'lucide-react';

const LANE_ICONS = {
    north: ArrowUp,
    south: ArrowDown,
    east: ArrowRight,
    west: ArrowLeft,
};

const LANE_COLORS = {
    north: { bg: 'from-emerald-500 to-green-600', border: 'border-emerald-400', text: 'text-emerald-100' },
    south: { bg: 'from-rose-500 to-red-600', border: 'border-rose-400', text: 'text-rose-100' },
    east: { bg: 'from-amber-500 to-yellow-600', border: 'border-amber-400', text: 'text-amber-100' },
    west: { bg: 'from-violet-500 to-purple-600', border: 'border-violet-400', text: 'text-violet-100' },
};

export default function LaneCard({ name, current, cumulative, direction, breakdown }) {
    const laneName = name.toLowerCase();
    const Icon = LANE_ICONS[laneName] || Car;
    const colors = LANE_COLORS[laneName] || LANE_COLORS.north;

    // Traffic level based on current count
    const getTrafficLevel = (count) => {
        if (count >= 15) return { label: 'HEAVY', color: 'bg-red-500/30 text-red-200' };
        if (count >= 8) return { label: 'MODERATE', color: 'bg-yellow-500/30 text-yellow-200' };
        if (count >= 1) return { label: 'LIGHT', color: 'bg-green-500/30 text-green-200' };
        return { label: 'CLEAR', color: 'bg-slate-500/30 text-slate-300' };
    };

    const level = getTrafficLevel(current);

    return (
        <div className={`bg-gradient-to-br ${colors.bg} rounded-2xl p-5 shadow-xl border-2 ${colors.border} relative overflow-hidden`}>
            {/* Direction indicator */}
            <div className="absolute top-2 right-2 opacity-20">
                <Icon className="w-16 h-16" />
            </div>

            {/* Lane name */}
            <div className="flex items-center gap-2 mb-3">
                <Icon className="w-5 h-5 text-white" />
                <h3 className="text-white font-bold text-sm tracking-wider">{name}</h3>
            </div>

            {/* Big count */}
            <div className="mb-3">
                <div className="text-5xl font-bold text-white">{current}</div>
                <div className={`text-xs ${colors.text}`}>vehicles now</div>
            </div>

            {/* Stats row */}
            <div className="flex items-center justify-between text-xs">
                <div>
                    <div className={colors.text}>Total Seen</div>
                    <div className="text-white font-bold text-lg">{cumulative}</div>
                </div>

                <div className="text-right">
                    <div className={colors.text}>Direction</div>
                    <div className="text-white font-bold uppercase text-xs">
                        {direction === 'incoming' ? '⬇ IN' : '⬆ OUT'}
                    </div>
                </div>
            </div>

            {/* Traffic level badge */}
            <div className={`mt-3 text-center py-1 rounded-full text-xs font-bold ${level.color}`}>
                {level.label}
            </div>

            {/* Breakdown if available */}
            {breakdown && Object.keys(breakdown).length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/20 flex flex-wrap gap-1">
                    {Object.entries(breakdown).map(([type, count]) => (
                        <span key={type} className="text-xs bg-black/30 text-white px-2 py-0.5 rounded-full">
                            {type}: {count}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}