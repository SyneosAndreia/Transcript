import { useState, useEffect } from 'react';
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
    Alert,
    FormControlLabel,
    Checkbox,
    IconButton
} from '@mui/material';
import { UploadFile, Close } from '@mui/icons-material';
import { transcriptionService } from './services/api';
import TranscriptResults from './components/TranscriptResults';

function App() {
    const [sourceType, setSourceType] = useState('');
    const [url, setUrl] = useState('');
    const [files, setFiles] = useState([])
    const [isProcessing, setIsProcessing] = useState(false);
    const [progress, setProgress] = useState({
        status: 'idle',
        message: '',
        progress: 0,
        segments: []
    });
    const [timeStamps, setTimeStamps] = useState(false);
    const [transcript, setTranscript] = useState(null);
    const [error, setError] = useState('');

    // Handle source type change
    const handleSourceChange = (e) => {
        setSourceType(e.target.value);
        setUrl('');
        setFiles([])
        setError('');
    };

    // Handle file selection
    const handleFileChange = (e) => {
        const selectedFiles = Array.from(e.target.files)
        setFiles(prev => [...prev, ...selectedFiles])
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
    }

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        // console.log(e.dataTransfer.files)
        const droppedFiles = Array.from(e.dataTransfer.files)
        setFiles(prev => [...prev, ...droppedFiles])
    }

    const removeFile = (index) => {
        setFiles(prev => {
            return prev.filter((_, i) => index !== i)
        })
    }

    const handleSubmit = async () => {
        try {
            setError('')
            setIsProcessing(true)
            setTranscript(null)
            setProgress({
                status: 'idle',
                message: '',
                progress: 0,
                segments: []
            });

            let response;
            if (sourceType === 'file') {
                const formData = new FormData();
                formData.append('type', sourceType)
                files.forEach(file => formData.append('files[]', file));
                response = await transcriptionService.processMedia(sourceType, formData);
            } else {
                response = await transcriptionService.processMedia(sourceType, url);
            }

            console.log('Response from server:', response);

            if (response.status === 'success') {
                setIsProcessing(false)
                if (response.transcripts) {
                    setTranscript({
                        status: 'success',
                        transcripts: response.transcripts
                    })
                } else {
                    setTranscript({
                        status: 'success',
                        transcript: response.transcript,
                        filename: response.filename,
                        transcript_path: response.transcript_path
                    });
                }

                // Clear form data
                setSourceType('');
                setUrl('');
                setFiles([]);
            }
        } catch (err) {
            console.error('Error in submission:', err);
            setError(err.message || 'An error occurred');
            setIsProcessing(false);
        }
    }

    const handleCancel = async () => {
        try {
            await transcriptionService.cancelTransCript();
            setSourceType('')
            setUrl('');
            setFiles([])
            setError('');
            setTranscript(null);
            setProgress({
                status: 'idle',
                message: '',
                progress: 0,
                segments: []
            });
        } catch (err) {
            console.error('Error canceling transcription:', err);
            setError(err.message || 'Error canceling transcription');
        }
    }

    useEffect(() => {
        let interval;

        const checkProgress = async () => {
            try {
                const progressData = await transcriptionService.getProgress();
                setProgress(progressData);

                if (progressData.status === 'complete' || progressData.status === 'error') {
                    // console.log("Stopping polling - status:", progressData.status);
                    setIsProcessing(false);
                    clearInterval(interval);
                } else if (progressData.status === 'error') {
                    clearInterval(interval);
                    setIsProcessing(false);
                    setError('Transcription failed');
                } 
            } catch (err) {
                setError(err.message || 'Error checking progress');
                setIsProcessing(false);
                clearInterval(interval);
            }
        }

        if (isProcessing) {
            checkProgress(); // Initial check
            interval = setInterval(checkProgress, 2000); // Poll every 2 seconds
        }

        return () => {
            if (interval) {
                // console.log("Cleanup: clearing polling interval");
                clearInterval(interval);
            }
        };
    }, [isProcessing]);

    const handleDownload = async (filename) => {
        if (!filename) {
            console.error('No filename provided for download');
            return;
        }

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

    return (
        <Container maxWidth="md" className="py-8">
            <Typography variant="h4" className="text-center" sx={{ mb: 4 }}>
                Video Transcription Tool
            </Typography>

            <Paper className="p-6">
                {/* Source Type Selection */}
                <FormControl fullWidth sx={{ mb: 2 }}>
                    {/* <FormControl fullWidth className="mb-4"> */}
                    <InputLabel>What would you like to transcribe?</InputLabel>
                    <Select
                        value={sourceType}
                        onChange={handleSourceChange}
                        label="What would you like to transcribe?"
                        disabled={isProcessing}
                    >
                        <MenuItem value="video">Single Video URL</MenuItem>
                        <MenuItem value="playlist">YouTube Playlist URL</MenuItem>
                        <MenuItem value="file">Upload Video/Audio File(s)</MenuItem>
                    </Select>
                </FormControl>

                {/* Input Fields */}
                {sourceType === 'file' ? (
                    <div>
                        <div
                            className='border-2 border-dashed border-gray-300 rounded-lg p-8 tex-center cursor-pointer hover:border-blue-500 transition-colors'
                            onClick={() => document.getElementById('file-upload').click()}
                            onDragOver={handleDragOver}
                            onDrop={handleDrop}
                        >
                            <UploadFile
                                sx={{
                                    width: 48,
                                    height: 48,
                                    margin: 'auto',
                                    color: 'text.secondary'
                                }}
                            />
                            <p>Drag and drop files here, or click to select files</p>
                            <input
                                id="file-upload"
                                type="file"
                                hidden
                                multiple
                                onChange={handleFileChange}
                                accept="audio/*,video/*"
                            />
                        </div>

                        {files.length > 0 && (
                            <div>
                                {files.map((file, index) => (
                                    <div key={index}>
                                        <span>{file.name}</span>
                                        <IconButton
                                            onClick={() => removeFile(index)}
                                            size="small"
                                            color="error"
                                        >
                                            <Close fontSize="small" />
                                        </IconButton>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
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

                <FormControlLabel control={<Checkbox checked={timeStamps} onChange={(e) => setTimeStamps(e.target.checked)} />} label="TimeStamps" />

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


                    </Box>
                )}

                {transcript && (
                    <>
                        {console.log('Transcript state before passing to component:', transcript)}
                        <TranscriptResults
                            transcript={transcript}
                            onDownload={handleDownload}
                        />

                    </>
                )}

                {/* Submit Button */}
                <div className='flex gap-20'>
                    <Button
                        variant="contained"
                        onClick={handleSubmit}
                        disabled={!!(isProcessing || !sourceType || (sourceType === 'file' ? files.length === 0 : !url) || transcript)}
                        fullWidth
                        sx={{ mt: 2 }}
                    >
                        Start Transcription
                    </Button>
                    {/* Submit Button */}
                    <Button
                        variant="contained"
                        onClick={handleCancel}
                        disabled={sourceType === ''}
                        fullWidth
                        color="error"
                        sx={{ mt: 2 }}
                    >
                        Cancel Transcription
                    </Button>

                </div>
            </Paper>
        </Container>
    );
}

export default App;