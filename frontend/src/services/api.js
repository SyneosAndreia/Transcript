// src/services/api.js
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || '/api';

export const transcriptionService = {
    // Upload file or process YouTube URL
    processMedia: async (type, data) => {
        if (!['video', 'playlist', 'file'].includes(type)) {
            throw new Error('Invalid media type')
        }
    
        const formData = new FormData();
        formData.append('type', type);
        
        if (type === 'file') {
            formData.append('file', data);
        } else {
            formData.append('source', data);
        }
    
        try {
            const response = await axios.post(`${API_URL}/process`, formData);
            return response.data;
        } catch (error) {
            console.error('Error details:', error.response?.data);
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
    },

    downloadTranscript: async (filename) => {
        try {
            console.log("Downloading file:", filename);
            console.log("Using API URL:", API_URL);
            const response = await axios.get(`${API_URL}/download/${filename}`, {
                responseType: 'blob'
            });
            if (response.status === 200) {
                return response.data;
            } else {
                throw new Error('Failed to download file');
            }
        } catch (error) {
            throw error.response?.data || error.message;
        }
    }
};