export default function SignalLight({ state = "GREEN" }) {
    const colors = {
        GREEN: { bg: "bg-green-500", glow: "shadow-green-500/50", text: "GO" },
        YELLOW: { bg: "bg-yellow-500", glow: "shadow-yellow-500/50", text: "SLOW" },
        RED: { bg: "bg-red-500", glow: "shadow-red-500/50", text: "STOP" },
    };

    const current = colors[state] || colors.GREEN;

    return (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <h3 className="text-slate-300 text-sm font-medium mb-4">Traffic Signal</h3>

            <div className="flex flex-col items-center gap-3 bg-slate-900 rounded-xl p-4">
                {/* Red light */}
                <div className={`w-16 h-16 rounded-full ${state === 'RED' ? 'bg-red-500 shadow-lg shadow-red-500/50' : 'bg-red-900/30'}`}></div>

                {/* Yellow light */}
                <div className={`w-16 h-16 rounded-full ${state === 'YELLOW' ? 'bg-yellow-500 shadow-lg shadow-yellow-500/50' : 'bg-yellow-900/30'}`}></div>

                {/* Green light */}
                <div className={`w-16 h-16 rounded-full ${state === 'GREEN' ? 'bg-green-500 shadow-lg shadow-green-500/50' : 'bg-green-900/30'}`}></div>
            </div>

            <div className={`mt-4 text-center py-2 rounded-lg ${current.bg} text-white font-bold text-lg shadow-lg ${current.glow}`}>
                {current.text}
            </div>
        </div>
    );
}