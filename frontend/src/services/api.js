// src/services/api.js
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || '/api';

export const transcriptionService = {
    // Upload file or process YouTube URL
    processMedia: async (type, data) => {
        if(!['video', 'playlist', 'file'].includes(type)) {
            throw new Error('Invalid media type')
        }

        const formData = new FormData();
        
        formData.append('type', type);
        console.log(formData)
        if (type === 'file') {
            formData.append('file', data);
        } else {
            formData.append('source', data);
        }

        try {
            const response = await axios.post(`${API_URL}/process`, formData);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    // Get progress updates
    getProgress: async () => {
        try {
            const response = await axios.get(`${API_URL}/progress`);
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    }
};