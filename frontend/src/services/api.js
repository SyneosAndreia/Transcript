import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// Create axios instance with default config
const api = axios.create({
    baseURL: API_URL,
    withCredentials: true,
    // headers: {
    //     'Content-Type': 'application/json'
    // }
});

export const transcriptionService = {
    processMedia: async (type, data) => {
        if (!['video', 'playlist', 'file'].includes(type)) {
            throw new Error('Invalid media type')
        }

        try {
            if (type === 'file' && data instanceof FormData) {
                console.log('Sending file FormData:', data);
                for (let pair of data.entries()) {
                    console.log(pair[0], pair[1]);
                }
                
                const response = await api.post('/process', data, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });
                return response.data;
            }

            const formData = new FormData();
            formData.append('type', type);
            formData.append('source', data);

            const response = await api.post('/process', formData, {
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

    getProgress: async () => {
        try {
            const response = await api.get('/progress');
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message;
        }
    },

    downloadTranscript: async (filename) => {
        try {
            console.log("Downloading file:", filename);
            console.log("Using API URL:", API_URL);
            const response = await api.get(`/download/${filename}`, {
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
            const response = await api.post('/cancel')
            return response.data;
        } catch (error) {
            throw error.response?.data || error.message
        }
    },

    testCORS: async () => {
        try {
            console.log('Testing CORS with API URL:', API_URL);
            
            const response = await api.options('/cors-debug', {
                headers: {
                    'Origin': window.location.origin,
                    'Access-Control-Request-Method': 'GET'
                }
            });

            console.log('CORS Test Response:', {
                status: response.status,
                headers: response.headers
            });

            return response;
        } catch (error) {
            console.error('CORS Test Error:', error);
            throw error;
        }
    }
};