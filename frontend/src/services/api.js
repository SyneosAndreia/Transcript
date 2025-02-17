// src/services/api.js
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export const transcriptionService = {
    // Upload file or process YouTube URL
    processMedia: async (type, data) => {
        if (!['video', 'playlist', 'file'].includes(type)) {
            throw new Error('Invalid media type')
        }
    
        const formData = new FormData();
        formData.append('type', type);

        if (type === 'file') {
            if(data instanceof FormData) {
                const response =  await axios.post(`${API_URL}/process`, data, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
            }

            // MULTIPLE FILES
            if(Array.isArray(data)) {
                data.forEach(file => {
                    formData.append('files[]', file);
                });
            } else {
                formData.append('files[]', data);
            }
        } else {
            formData.append('source', data);
        }

        try {
            const response = await axios.post(`${API_URL}/process`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            console.log('Server response:', response.data);
            return response.data;
        } catch (error) {
            console.log('Error details:', error.response?.data);
            throw error.response?.data || error.message
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
                responseType: 'blob',
                headers: {
                    'Accept': 'application/octet-stream',
                },
            });
            if (response.status === 200) {
                return response.data;
            } else {
                throw new Error('Failed to download file');
            }
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    cancelTransCript: async () => {
        try {
            const response = await axios.post(`${API_URL}/cancel`)
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message
        }
    }
};