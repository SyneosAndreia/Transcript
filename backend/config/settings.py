import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    UPLOAD_FOLDER = 'uploads'
    TEMP_FOLDER = 'temp_audio'
    TRANSCRIPTS_FOLDER = 'transcripts'
    ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'm4a'}

    FIREBASE_AUDIO_FOLDER = 'audio'
    FIREBASE_TRANSCRIPT_FOLDER = 'transcripts'

    ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
    USE_FIREBASE = ENVIRONMENT == 'production'

    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    FIREBASE_CREDENTIALS = os.environ.get('FIREBASE_CREDENTIALS')

    ALLOWED_ORIGINS = os.getenv(
        'ALLOWED_ORIGINS',
        'http://localhost:5173,https://transcript-delta.vercel.app'
    ).split(',')