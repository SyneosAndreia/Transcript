import { useState, useEffect } from 'react';
import axios from 'axios';
import {
    Container,
    Box,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Button,
    Paper,
    LinearProgress,
    Typography,
    Alert
} from '@mui/material';
import { transcriptionService } from './services/api';
import { API_URL } from './services/api';
import TranscriptResults from './components/TranscriptResults';

function App() {
    const [sourceType, setSourceType] = useState('');
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [progress, setProgress] = useState({
        status: 'idle',
        message: '',
        progress: 0,
        segments: []
    });
    const [transcript, setTranscript] = useState(null);

    const [error, setError] = useState('');

    // Handle source type change
    const handleSourceChange = (e) => {
        setSourceType(e.target.value);
        setUrl('');
        setFile(null);
        setError('');
    };

    // Handle file selection
    const handleFileChange = (e) => {
        if (e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    // Start processing
    const handleSubmit = async () => {
        try {
            setError('');
            setIsProcessing(true);
            setTranscript(null);
            setProgress({
                status: 'idle',
                message: '',
                progress: 0,
                segments: []
            })

            // Send data based on source type
            const response = await transcriptionService.processMedia(
                sourceType,
                sourceType === 'file' ? file : url
            );

            if (response.status === 'success') {
                setTranscript(response)
            }

        } catch (err) {
            setError(err.message || 'An error occurred');
            setIsProcessing(false);
        }
    };

    useEffect(() => {
        let interval;

        if (isProcessing) {
            interval = setInterval(async () => {
                try {
                    console.log("Polling for progress..."); // Debug log
                    const progressData = await transcriptionService.getProgress();
                    console.log("Received progress data:", progressData); // Debug log

                    setProgress(progressData);

                    if (progressData.status === 'complete' || progressData.status === 'error') {
                        setIsProcessing(false);
                    }
                } catch (err) {
                    console.error("Error in polling:", err); // Debug error log
                    setError(err.message || 'Error checking progress');
                    setIsProcessing(false);
                }
            }, 1000);
        }

        // Cleanup function
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [isProcessing]);

    const handleDownload = async (filename) => {
        // try {
        //     const response = await axios.get(`${API_URL}/download/${filename}`, {
        //         responseType: 'blob'  // Important for file downloads
        //     });

        //     // Create a download link
        //     const url = window.URL.createObjectURL(new Blob([response.data]));
        //     const link = document.createElement('a');
        //     link.href = url;
        //     link.setAttribute('download', filename);
        //     document.body.appendChild(link);
        //     link.click();
        //     link.remove();
        //     window.URL.revokeObjectURL(url);
        // } catch (error) {
        //     console.error('Download error:', error);
        // }
        if (!filename) {
            console.error('No filename provided for download');
            return;
        }


        console.log("Downloading file:", filename);
        console.log("Using API URL:", API_URL);


        try {
            const blob = await transcriptionService.downloadTranscript(filename);
            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Download error:', error);
        }
    };

    // Poll progress
    const pollProgress = () => {
        const interval = setInterval(async () => {
            try {
                console.log("Polling for progress..."); // Debug log
                const progressData = await transcriptionService.getProgress();
                console.log("Received progress data:", progressData); // Debug log
                console.log("Segments:", progressData.segments); // Debug log

                setProgress(progressData);

                if (progressData.status === 'complete' || progressData.status === 'error') {
                    clearInterval(interval);
                    setIsProcessing(false);
                }
            } catch (err) {
                console.error("Error in polling:", err);
                clearInterval(interval);
                setError(err.message || 'Error checking progress');
                setIsProcessing(false);
            }
        }, 1000);
    };

    return (
        <Container maxWidth="md" className="py-8">
            <Typography variant="h4" className="text-center mb-8">
                Video Transcription Tool
            </Typography>

            <Paper className="p-6">
                {/* Source Type Selection */}
                <FormControl fullWidth className="mb-4">
                    <InputLabel>What would you like to transcribe?</InputLabel>
                    <Select
                        value={sourceType}
                        onChange={handleSourceChange}
                        label="What would you like to transcribe?"
                        disabled={isProcessing}
                    >
                        <MenuItem value="video">Single Video URL</MenuItem>
                        <MenuItem value="playlist">YouTube Playlist URL</MenuItem>
                        <MenuItem value="file">Upload Video/Audio File</MenuItem>
                    </Select>
                </FormControl>

                {/* Input Fields */}
                {sourceType === 'file' ? (
                    <Button
                        variant="contained"
                        component="label"
                        disabled={isProcessing}
                        className="mb-4"
                        fullWidth
                    >
                        Upload File
                        <input
                            type="file"
                            hidden
                            onChange={handleFileChange}
                            accept="audio/*,video/*"
                        />
                    </Button>
                ) : (
                    sourceType && (
                        <TextField
                            fullWidth
                            label={sourceType === 'video' ? 'YouTube Video URL' : 'YouTube Playlist URL'}
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={isProcessing}
                            className="mb-4"
                        />
                    )
                )}

                {/* Progress and Error Display */}
                {error && (
                    <Alert severity="error" className="mb-4">
                        {error}
                    </Alert>
                )}

                {isProcessing && (
                    <Box className="mb-4">
                        <LinearProgress
                            variant="determinate"
                            value={progress.progress}
                            className="mb-2"
                        />
                        <Typography variant="body2" color="textSecondary">
                            {progress.message}
                        </Typography>

                        {progress.segments && progress.segments.length > 0 && (
                            <Paper>
                                {progress.segments.map((segment, index) => (
                                    <Box key={index}>
                                        <Typography
                                            component="div"
                                            variant='body2'
                                        >
                                            <span>
                                                [{segment.start} --&gt; {segment.end}]
                                            </span>
                                            <span>
                                                {segment.text}
                                            </span>
                                        </Typography>
                                    </Box>

                                ))}
                            </Paper>




                            // <TranscriptionProgress segments={progress.segments}/>
                        )}
                    </Box>
                )}

                {/* {transcript && (
                    <Box className="mb-4">
                        <Alert severity="success" className='mb-2'>
                            Transcription completed successfully!
                        </Alert>
                        <Button
                            variant="contained"
                            color="secondary"
                            onClick={() => {
                                console.log("Transcript data:", transcript); // Add this log
                                handleDownload(transcript.filename);
                            }}
                            fullWidth
                            className='mb-2'
                        >Download Transcript
                        </Button>
                        <Typography variant="body2" className="mt-2 p-4 bg-gray-50 rounded">
                            {transcript.transcript}
                        </Typography>

                    </Box>
                )} */}

                {transcript && (
                    <TranscriptResults
                        transcript={transcript}
                        onDownload={handleDownload}
                    />
                )}

                {/* Submit Button */}
                <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={isProcessing || !sourceType || (!url && !file)}
                    fullWidth
                >
                    Start Transcription
                </Button>
            </Paper>
        </Container>
    );
}

export default App;