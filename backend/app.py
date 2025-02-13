from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import whisper
import os
from werkzeug.utils import secure_filename
import time
from datetime import datetime
import traceback
import stat
import shutil
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

import firebase_admin
from firebase_admin import credentials, storage, initialize_app

# Configuration =============================================================================
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp_audio'
TRANSCRIPTS_FOLDER = 'transcripts'
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'm4a'}

#Firebase folder config
FIREBASE_AUDIO_FOLDER = 'audio'
FIREBASE_TRANSCRIPT_FOLDER = 'transcripts'

ENVIRONMENT = os.getenv('FLASK_ENV', 'development')  # 'development' or 'production'
USE_FIREBASE = ENVIRONMENT == 'production'  # True if in production, False in development


# Load environment variables
load_dotenv()
try:
    # Try to get credentials from environment variable
    if os.getenv('FIREBASE_CREDENTIALS'):
        cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback to file for local development
        firebase_key_path = os.path.join('firebase', 'datavendor-prod-firebase-adminsdk-vkrda-73eabc949e.json')
        cred = credentials.Certificate(firebase_key_path)

    # Get storage bucket from environment variable or use default
    storage_bucket = os.getenv('FIREBASE_STORAGE_BUCKET', 'datavendor-prod.firebasestorage.app')

    # Initialize Firebase app
    firebase_admin.initialize_app(cred, {
        'storageBucket': storage_bucket
    })
    
    bucket = storage.bucket()
    logger.info("Firebase initialized successfully")
    
except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}")
    raise

#Firebase Helpers ===========================================================================
def save_to_firebase(file_data, folder, filename):
    """save files to firebase"""
    blob = bucket.blob(f"{folder}/{filename}")
    blob.upload_from_string(file_data)
    blob.make_public()
    return blob.public_url

def delete_from_firebase(file_path):
    """delete files from firebase"""
    try:
        blob = bucket.blob(file_path)
        blob.delete()
    except Exception as e:
        print(f"Error deleting file from Firebase: {e}")

def download_from_firebase(firebase_path, local_path):
    """Download file from Firebase to local path"""
    try:
        blob = bucket.blob(firebase_path)
        blob.download_to_filename(local_path)
        return True
    except Exception as e:
        print(f"Error downloading from Firebase: {e}")
        return False
    
def save_file(file_data, folder, filename, use_firebase= USE_FIREBASE):
    if use_firebase:
        return save_to_firebase(file_data, folder, filename)
    else:
        # Save locally
        local_path = os.path.join(folder, filename)
        if isinstance(file_data, bytes):
            with open(local_path, 'wb') as f:
                f.write(file_data)
        else:
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(file_data)
        return local_path
def delete_file(file_path, use_firebase=USE_FIREBASE):
    """Delete file from either Firebase or local storage"""
    if use_firebase:
        return delete_from_firebase(file_path)
    else:
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error deleting local file: {e}")
            return False

def download_file(source_path, local_path, use_firebase=USE_FIREBASE):
    """Download/copy file to local path from either Firebase or local storage"""
    if use_firebase:
        return download_from_firebase(source_path, local_path)
    else:
        try:
            shutil.copy2(source_path, local_path)
            return True
        except Exception as e:
            print(f"Error copying local file: {e}")
            return False


app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins temporarily
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})


# Clear and recreate directories
for folder in [UPLOAD_FOLDER, TEMP_FOLDER, TRANSCRIPTS_FOLDER]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    # Give full permissions
    os.chmod(folder, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "Transcription API is running"
    })

@app.route('/api/debug')
def debug():
    return jsonify({
        "folders": {
            "upload_folder": {
                "exists": os.path.exists(UPLOAD_FOLDER),
                "path": os.path.abspath(UPLOAD_FOLDER)
            },
            "temp_folder": {
                "exists": os.path.exists(TEMP_FOLDER),
                "path": os.path.abspath(TEMP_FOLDER)
            },
            "transcripts_folder": {
                "exists": os.path.exists(TRANSCRIPTS_FOLDER),
                "path": os.path.abspath(TRANSCRIPTS_FOLDER)
            }
        }
    })



# At the start, after the folder definitions
# Clean up any nested temp_audio folders
nested_temp = os.path.join(TEMP_FOLDER, 'temp_audio')
if os.path.exists(nested_temp):
    shutil.rmtree(nested_temp)



# Global progress tracking
current_progress = {
    'status': 'idle',
    'message': '',
    'progress': 0,
    'current_text': '',
    'segments': []
}

def update_progress(message, progress=None, segment=None):
    """Update the global progress tracker"""
    print(f"Progress Update: {message} - {progress}%")  # Debug print
    current_progress['message'] = message
    if progress is not None:
        current_progress['progress'] = progress
    if segment is not None:
        if 'segments' not in current_progress:
            current_progress['segments'] = []
        current_progress['segments'].append(segment);

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def download_audio(url, output_path=TEMP_FOLDER):
    """Download audio from YouTube video"""
    try:
        print(f"Starting download from URL: {url}")
        update_progress("Starting download...", 0)
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    percent = float(d['_percent_str'].replace('%', ''))
                    update_progress(
                        f"Downloading: {d['_percent_str']} at {d.get('_speed_str', 'N/A')}", 
                        int(percent)
                    )
                except:
                    update_progress(f"Downloading... {d.get('_speed_str', 'N/A')}")
            elif d['status'] == 'error':
                update_progress(f"Error: {d.get('error', 'Unknown error')}")
            elif d['status'] == 'finished':
                update_progress("Download complete, processing audio...", 100)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_template = f"audio_{timestamp}.%(ext)s"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_path, output_template),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            'progress_hooks': [progress_hook],
            'verbose': True,
            'no_warnings': False,
            # New options to try bypassing restrictions
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['android', 'web'],
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Starting download with yt-dlp...")
            info = ydl.extract_info(url, download=True)
            title = info['title']
            filename = os.path.join(output_path, f"audio_{timestamp}.mp3")
            
            # Wait briefly for file processing
            time.sleep(2)
            
            if not os.path.exists(filename):
                print(f"Looking for file in: {output_path}")
                files = os.listdir(output_path)
                print(f"Files in directory: {files}")
                raise FileNotFoundError(f"Downloaded file not found: {filename}")
                
            file_size = os.path.getsize(filename)
            print(f"Download complete: {filename} (Size: {file_size} bytes)")
            
            if file_size == 0:
                raise Exception("Downloaded file is empty")
                
            return filename, title
            
    except Exception as e:
        error_message = str(e)
        if "Sign in to confirm you're not a bot" in error_message:
            error_message = "YouTube is requiring verification. Please try uploading a file directly instead of using a URL, or try a different video."
        print(f"Download error: {error_message}")
        print(traceback.format_exc())
        update_progress(f"Error downloading audio: {str(e)}")
        return None, None

def get_playlist_videos(url):
    """Get all video URLs from a YouTube playlist"""
    try:
        print(f"Fetching playlist information from: {url}")  # Debug print
        update_progress("Fetching playlist information...")
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'force_generic_extractor': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            if 'entries' in result:
                videos = [entry['url'] for entry in result['entries']]
                print(f"Found {len(videos)} videos in playlist")  # Debug print
                return videos
            else:
                print("No playlist entries found, treating as single video")  # Debug print
                return [result['webpage_url']]
    except Exception as e:
        print(f"Playlist error: {str(e)}")  # Debug print
        print(traceback.format_exc())
        update_progress(f"Error getting playlist: {str(e)}")
        return []

def transcribe_audio(audio_file, source_info=""):
    """Transcribe audio file using Whisper"""
    try:
        print(f"Starting transcription of: {audio_file}")
        update_progress("Loading Whisper model...", 30)
        
        # Check if file exists
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
        # Check file size
        file_size = os.path.getsize(audio_file)
        print(f"File size: {file_size} bytes")
        
        # Load model with explicit device setting
        model = whisper.load_model("base", device="cpu")
        print("Model loaded successfully")
        
        update_progress("Starting transcription...", 40)
        result = model.transcribe(
            audio_file,
            verbose=True,
            language='en',
            fp16=False  # Explicitly disable FP16
        )

        # Process segments in real-time
        for segment in result['segments']:
            start = f"{int(segment['start'] // 60):02d}:{segment['start'] % 60:06.3f}"
            end = f"{int(segment['end'] // 60):02d}:{segment['end'] % 60:06.3f}"
            
            # Update progress with each segment
            update_progress(
                "Transcribing...", 
                progress=40 + (segment['end'] / result['segments'][-1]['end']) * 50,
                segment={
                    'start': start,
                    'end': end,
                    'text': segment['text'].strip()
                }
            )

        print("Transcription complete")
        
        # Save transcript
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        transcript_file = f"{TRANSCRIPTS_FOLDER}/{timestamp}_{base_name}.txt"
        
        with open(transcript_file, "w", encoding="utf-8") as f:
            if source_info:
                f.write(f"Source: {source_info}\n\n")

            # Write timestamped segments from current_progress
            # for segment in current_progress['segments']:
            #     f.write(f"[{segment['start']} --> {segment['end']}] {segment['text']}\n")

            # f.write("\n\nFull Transcript:\n")
            f.write(result["text"])
        
        print(f"Transcript saved to: {transcript_file}")
        return transcript_file, result["text"]
        
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        print(f"Error type: {type(e)}")
        print(traceback.format_exc())
        update_progress(f"Error in transcription: {str(e)}")
        return None, None
@app.route('/api/progress')
def get_progress():
    """Get current progress status"""
    return jsonify(current_progress)


@app.route('/api/process', methods=['POST'])
def process_media():
    """Process uploaded file or YouTube URL"""
    audio_file = None
    try:
        print("Starting process_media...")
        source_type = request.form.get('type')
        print(f"Source type: {source_type}")
        
        current_progress['status'] = 'processing'
        update_progress("Starting process...", 0)
        
        if source_type == 'video':
            source_url = request.form.get('source')
            print(f"Processing URL: {source_url}")
            
            if not source_url:
                return jsonify({'error': 'No URL provided'}), 400
            
            # Download the audio
            audio_file, title = download_audio(source_url)
            
            if audio_file and os.path.exists(audio_file):
                print(f"Audio file exists at: {audio_file}")
                
                # Save audio file to storage
                with open(audio_file, 'rb') as f:
                    audio_filename = os.path.basename(audio_file)
                    stored_audio_path = save_file(
                        f.read(), 
                        FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
                        audio_filename
                    )
                
                # Transcribe
                transcript_file, text = transcribe_audio(
                    audio_file,
                    f"Video: {title}\nURL: {source_url}"
                )
                
                if transcript_file:
                    # Save transcript to storage
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_content = f.read()
                    transcript_filename = os.path.basename(transcript_file)
                    stored_transcript_path = save_file(
                        transcript_content,
                        FIREBASE_TRANSCRIPT_FOLDER if USE_FIREBASE else TRANSCRIPTS_FOLDER,
                        transcript_filename
                    )
                    
                    # Clean up local files
                    delete_file(audio_file)
                    # delete_file(transcript_file)
                    
                    print("Process completed successfully")
                    update_progress("Processing complete!", 100)
                    current_progress['status'] = 'complete'
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Processing complete',
                        'transcript': text,
                        'filename': transcript_filename,
                        'transcript_path': stored_transcript_path
                    })
                else:
                    raise Exception("Transcription failed")
            else:
                raise Exception("Audio download failed or file not found")

        elif source_type == 'playlist':
            source_url = request.form.get('source')
            print(f"Processing playlist URL: {source_url}")
            
            if not source_url:
                return jsonify({'error': 'No URL provided'}), 400
            
            videos = get_playlist_videos(source_url)
            update_progress(f"Found {len(videos)} videos in playlist", 10)
            
            all_transcripts = []
            
            for idx, video_url in enumerate(videos, 1):
                update_progress(f"Processing video {idx}/{len(videos)}")
                audio_file, title = download_audio(video_url)
                
                if audio_file:
                    # Save audio to storage
                    with open(audio_file, 'rb') as f:
                        audio_filename = os.path.basename(audio_file)
                        stored_audio_path = save_file(
                            f.read(),
                            FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
                            audio_filename
                        )
                    
                    transcript_file, text = transcribe_audio(
                        audio_file, 
                        f"Video {idx}: {title}\nURL: {video_url}"
                    )
                    
                    if transcript_file:
                        # Save transcript to storage
                        with open(transcript_file, 'r', encoding='utf-8') as f:
                            transcript_content = f.read()
                        transcript_filename = os.path.basename(transcript_file)
                        stored_transcript_path = save_file(
                            transcript_content,
                            FIREBASE_TRANSCRIPT_FOLDER if USE_FIREBASE else TRANSCRIPTS_FOLDER,
                            transcript_filename
                        )
                        
                        all_transcripts.append({
                            'title': title,
                            'text': text,
                            'path': stored_transcript_path
                        })
                        
                        # Clean up local files
                        delete_file(audio_file)
                        delete_file(transcript_file)
            
            if all_transcripts:
                print("Playlist processing completed successfully")
                update_progress("Processing complete!", 100)
                current_progress['status'] = 'complete'
                return jsonify({
                    'status': 'success',
                    'message': 'Playlist processing complete',
                    'transcripts': all_transcripts
                })
            else:
                raise Exception("No transcripts were generated")
                
        elif source_type == 'file':
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed'}), 400
            
            # Save uploaded file
            filename = secure_filename(file.filename)
            stored_audio_path = save_file(
                file.read(),
                FIREBASE_AUDIO_FOLDER if USE_FIREBASE else UPLOAD_FOLDER,
                filename
            )
            
            # If using Firebase, need to download for processing
            if USE_FIREBASE:
                temp_path = os.path.join(TEMP_FOLDER, filename)
                download_file(stored_audio_path, temp_path)
                process_path = temp_path
            else:
                process_path = stored_audio_path
            
            # Transcribe
            transcript_file, text = transcribe_audio(process_path, f"Uploaded file: {filename}")
            
            if transcript_file:
                # Save transcript
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript_content = f.read()
                transcript_filename = os.path.basename(transcript_file)
                stored_transcript_path = save_file(
                    transcript_content,
                    FIREBASE_TRANSCRIPT_FOLDER if USE_FIREBASE else TRANSCRIPTS_FOLDER,
                    transcript_filename
                )
                
                # Clean up
                if USE_FIREBASE:
                    delete_file(temp_path)
                delete_file(transcript_file)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Processing complete',
                    'transcript': text,
                    'transcript_path': stored_transcript_path
                })
            else:
                raise Exception("Transcription failed")
        
    except Exception as e:
        print(f"Process error: {str(e)}")
        print(traceback.format_exc())
        current_progress['status'] = 'error'
        update_progress(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500  

@app.route('/api/download/<filename>')
def download_transcript(filename):
    """Download a transcript file"""
    try:
        print(f"Download request received for file: {filename}")
        print(f"Storage mode: {'Firebase' if USE_FIREBASE else 'Local'}")
        
        safe_filename = secure_filename(filename)
        if USE_FIREBASE:
            print(f"Attempting to download from Firebase path: {FIREBASE_TRANSCRIPT_FOLDER}/{safe_filename}")
            temp_path = os.path.join(TEMP_FOLDER, safe_filename)
            firebase_path = f"{FIREBASE_TRANSCRIPT_FOLDER}/{safe_filename}"
            
            if download_file(firebase_path, temp_path, use_firebase=True):
                print(f"File downloaded to temp path: {temp_path}")
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='text/plain'  # Added explicit mimetype
                )
            else:
                print("File not found in Firebase")
                return jsonify({'error': 'File not found in Firebase'}), 404
        else:
            safe_path = os.path.join(TRANSCRIPTS_FOLDER, safe_filename)
            print(f"Attempting to download from local path: {safe_path}")
            if os.path.exists(safe_path):
                return send_file(
                    safe_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='text/plain'  # Added explicit mimetype
                )
            else:
                print("File not found locally")
                return jsonify({'error': 'File not found'}), 404
                
    except Exception as e:
        print(f"Download error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)