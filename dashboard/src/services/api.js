import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: API_URL,
    timeout: 5000,
});

// Get traffic data for an intersection
export const getTrafficData = async (intersectionId = 'intersection_1') => {
    const response = await api.get(`/traffic/${intersectionId}`);
    return response.data;
};

// Get history
export const getHistory = async (intersectionId = 'intersection_1') => {
    const response = await api.get(`/traffic/${intersectionId}/history`);
    return response.data;
};

// Get all intersections
export const getIntersections = async () => {
    const response = await api.get('/intersections');
    return response.data;
};

// Manual override - reset
export const resetIntersection = async (intersectionId = 'intersection_1') => {
    const response = await api.delete(`/traffic/${intersectionId}/reset`);
    return response.data;
};

// Manual update
export const updateTraffic = async (intersectionId, count) => {
    const response = await api.post(
        `/traffic/${intersectionId}/update`,
        null,
        { params: { vehicle_count: count } }
    );
    return response.data;
};

export default api;