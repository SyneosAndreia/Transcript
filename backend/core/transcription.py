import whisper
from datetime import datetime
import os
from utils.logger import logger

class Transcriber:
    def __init__(self, config, progress_tracker):
        self.config = config
        self.progress = progress_tracker
        
        # Determine transcripts folder
        # Look for TRANSCRIPTS_FOLDER in multiple ways
        if hasattr(config, 'TRANSCRIPTS_FOLDER'):
            self.transcripts_folder = config.TRANSCRIPTS_FOLDER
        elif isinstance(config, dict):
            self.transcripts_folder = config.get('TRANSCRIPTS_FOLDER', 'transcripts')
        else:
            self.transcripts_folder = 'transcripts'
        
        # Ensure the transcripts folder exists
        os.makedirs(self.transcripts_folder, exist_ok=True)
        
    def transcribe_audio(self, audio_file, source_info=""):
        """Transcribe audio file using Whisper"""
        try:
            logger.info(f"Starting transcription of: {audio_file}")
            self.progress.update("Loading Whisper model...", 30)
            
            # Additional file validation
            if not os.path.exists(audio_file):
                raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
            file_size = os.path.getsize(audio_file)
            logger.info(f"File size: {file_size} bytes")

            model = whisper.load_model("base", device="cpu")
            self.progress.update("Starting transcription...", 40)
            
            result = model.transcribe(
                audio_file,
                verbose=True,
                language='en',
                fp16=False
            )

            # Process segments
            for segment in result['segments']:
                start = f"{int(segment['start'] // 60):02d}:{segment['start'] % 60:06.3f}"
                end = f"{int(segment['end'] // 60):02d}:{segment['end'] % 60:06.3f}"
                
                self.progress.update(
                    "Transcribing...", 
                    progress=40 + (segment['end'] / result['segments'][-1]['end']) * 50,
                    segment={
                        'start': start,
                        'end': end,
                        'text': segment['text'].strip()
                    }
                )

            # Save transcript
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(audio_file))[0]


            # Ensure transcripts folder exists
            os.makedirs(self.transcripts_folder, exist_ok=True)
            
            transcript_file = os.path.join(
                self.transcripts_folder, 
                f"{timestamp}_{base_name}_transcript.txt"
            )
            
            logger.info(f"Attempting to save transcript to: {transcript_file}")
            
            with open(transcript_file, "w", encoding="utf-8") as f:
                if source_info:
                    f.write(f"Source: {source_info}\n\n")
                f.write(result["text"])
            
            logger.info(f"Transcript saved successfully to: {transcript_file}")
            
            return transcript_file, result["text"]
            
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            logger.error(traceback.format_exc())
            self.progress.update(f"Error in transcription: {str(e)}")
            return None, None

