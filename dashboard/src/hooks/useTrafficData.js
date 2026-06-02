import { useState, useEffect } from 'react';
import { getTrafficData, getHistory } from '../services/api';

export function useTrafficData(intersectionId = 'intersection_1', interval = 2000) {
    const [data, setData] = useState(null);
    const [history, setHistory] = useState([]);
    const [isOnline, setIsOnline] = useState(false);
    const [error, setError] = useState(null);

    const fetchData = async () => {
        try {
            const [current, hist] = await Promise.all([
                getTrafficData(intersectionId),
                getHistory(intersectionId),
            ]);
            setData(current);
            setHistory(hist.history || []);
            setIsOnline(true);
            setError(null);
        } catch (err) {
            setIsOnline(false);
            setError(err.message);
        }
    };

    useEffect(() => {
        fetchData();
        const timer = setInterval(fetchData, interval);
        return () => clearInterval(timer);
    }, [intersectionId, interval]);

    return { data, history, isOnline, error, refetch: fetchData };
}