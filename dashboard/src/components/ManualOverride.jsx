import { useState } from 'react';
import { AlertTriangle, RefreshCw, Send } from 'lucide-react';
import { resetIntersection, updateTraffic } from '../services/api';

export default function ManualOverride({ intersectionId, onUpdate }) {
    const [manualCount, setManualCount] = useState('');
    const [loading, setLoading] = useState(false);

    const handleReset = async () => {
        setLoading(true);
        try {
            await resetIntersection(intersectionId);
            onUpdate();
        } catch (err) {
            console.error('Reset failed:', err);
        }
        setLoading(false);
    };

    const handleManualUpdate = async () => {
        if (!manualCount) return;
        setLoading(true);
        try {
            await updateTraffic(intersectionId, parseInt(manualCount));
            setManualCount('');
            onUpdate();
        } catch (err) {
            console.error('Update failed:', err);
        }
        setLoading(false);
    };

    return (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-orange-400" />
                <h3 className="text-white text-lg font-bold">Manual Override</h3>
            </div>

            <div className="space-y-3">
                <div className="flex gap-2">
                    <input
                        type="number"
                        value={manualCount}
                        onChange={(e) => setManualCount(e.target.value)}
                        placeholder="Enter vehicle count"
                        className="flex-1 bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-blue-500 focus:outline-none"
                    />
                    <button
                        onClick={handleManualUpdate}
                        disabled={loading || !manualCount}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 disabled:opacity-50"
                    >
                        <Send className="w-4 h-4" />
                        Set
                    </button>
                </div>

                <button
                    onClick={handleReset}
                    disabled={loading}
                    className="w-full bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    Reset Intersection
                </button>
            </div>

            <p className="text-xs text-slate-400 mt-3">
                ⚠️ Manual override logs to blockchain audit trail
            </p>
        </div>
    );
}