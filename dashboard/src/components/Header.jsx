import { Activity } from 'lucide-react';

export default function Header({ isOnline }) {
    return (
        <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
            <div className="max-w-7xl mx-auto flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="text-3xl">🚦</div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">SMART_ROUTE</h1>
                        <p className="text-xs text-slate-400">Decentralized Adaptive Traffic Control</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Activity className={`w-4 h-4 ${isOnline ? 'text-green-400' : 'text-red-400'} animate-pulse`} />
                    <span className="text-sm text-slate-300">
                        {isOnline ? 'Connected' : 'Disconnected'}
                    </span>
                </div>
            </div>
        </header>
    );
}