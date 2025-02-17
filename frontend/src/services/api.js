// src/services/api.js
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export const transcriptionService = {
    // Upload file or process YouTube URL
    
    processMedia: async (type, data) => {
        if (!['video', 'playlist', 'file'].includes(type)) {
            throw new Error('Invalid media type')
        }

        try {
            // For file uploads, just send the FormData directly
            if (type === 'file' && data instanceof FormData) {
                console.log('Sending file FormData:', data);
                // Log the content of FormData for debugging
                for (let pair of data.entries()) {
                    console.log(pair[0], pair[1]);
                }
                
                const response = await axios.post(`${API_URL}/process`, data, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
                return response.data;
            }

            // For other types (video, playlist)
            const formData = new FormData();
            formData.append('type', type);
            formData.append('source', data);

            const response = await axios.post(`${API_URL}/process`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
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