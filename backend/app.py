from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
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


# Set up logging - alternative to print or console.log in JS
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'  # Adds timestamp and log level
)
logger = logging.getLogger(__name__)


import firebase_admin
from firebase_admin import credentials, storage, initialize_app



# Environment variables 
FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
FIREBASE_CREDENTIALS = os.environ.get('FIREBASE_CREDENTIALS')

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


# Debug
print("Environment variables check:")
print("FIREBASE_STORAGE_BUCKET:", os.environ.get('FIREBASE_STORAGE_BUCKET'))
print("FIREBASE_CREDENTIALS exists:", bool(os.environ.get('FIREBASE_CREDENTIALS')))
print("FLASK_ENV:", os.environ.get('FLASK_ENV'))




for folder in [UPLOAD_FOLDER, TEMP_FOLDER, TRANSCRIPTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        logger.info(f"Created folder: {folder}")

# Load Firebase environment variables
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
    try:
        # Add FIREBASE_AUDIO_FOLDER if not already included
        if not file_path.startswith(FIREBASE_AUDIO_FOLDER):
            file_path = f"{FIREBASE_AUDIO_FOLDER}/{file_path}"
        blob = bucket.blob(file_path)
        blob.delete()
    except Exception as e:
        print(f"Error deleting file from Firebase: {e}")

def download_from_firebase(firebase_path, local_path):
    """Download file from Firebase to local path"""
    try:
        logger.info(f"🔥 Downloading from Firebase")
        logger.info(f"Firebase path: {firebase_path}")
        logger.info(f"Local destination: {local_path}")
        
        # Create TEMP_FOLDER if it doesn't exist
        os.makedirs(TEMP_FOLDER, exist_ok=True)
        
        # Ensure we're looking in the audio folder in Firebase
        if not firebase_path.startswith(FIREBASE_AUDIO_FOLDER):
            firebase_path = f"{FIREBASE_AUDIO_FOLDER}/{firebase_path}"
        
        logger.info(f"Complete Firebase path: {firebase_path}")
        
        blob = bucket.blob(firebase_path)
        
        # Log blob details
        logger.info(f"Blob exists: {blob.exists()}")
        if not blob.exists():
            logger.error(f"Blob not found in Firebase: {firebase_path}")
            return False
            
        logger.info(f"Blob public URL: {blob.public_url}")
        
        blob.download_to_filename(local_path)
        
        logger.info(f"✅ Download successful to {local_path}")
        logger.info(f"Local file exists: {os.path.exists(local_path)}")
        logger.info(f"Local file size: {os.path.getsize(local_path)} bytes")
        
        return True
    except Exception as e:
        logger.error(f"Error downloading from Firebase: {e}")
        logger.error(traceback.format_exc())
        return False
     
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
    normalized_source_path = os.path.normpath(source_path)
    
    logger.info(f"Looking for file at: {os.path.abspath(normalized_source_path)}")

    if use_firebase:
        logger.info(f"📡 Fetching from Firebase: {source_path}")
        return download_from_firebase(normalized_source_path, local_path)
    else:
        try:
            logger.info(f"📁 Copying local file from {normalized_source_path} to {local_path}")
            shutil.copy2(normalized_source_path, local_path)
            if os.path.exists(normalized_source_path):
                shutil.copy2(normalized_source_path, local_path)
                logger.info(f"✅ Copy successful: {local_path}")
                return True
            else:
                logger.error(f"File does not exist at: {normalized_source_path}")
                return False
        except Exception as e:
            logger.info(f"Error copying local file: {e}")
            return False


# 2. Configuration and Setup
app = Flask(__name__)

@app.route('/health')
@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'cors_config': {
            'allowed_origins': ALLOWED_ORIGINS
        }
    }), 200

# CORS(app, resources={
#     r"/api/*": {
#         "origins": ["http://localhost:5173", "https://transcript-delta.vercel.app/"],
#         "methods": ["GET", "POST", "OPTIONS"],  # Added OPTIONS
#         "allow_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin"],
#         "expose_headers": ["Content-Disposition", "Access-Control-Allow-Origin"],
#         "supports_credentials": True,
#         "max_age": 600
#     }
# })
# Get allowed origins from environment variables
# Default to localhost if not set
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173').split(',')

CORS(app, resources={
    r"/api/*": {
        "origins": ["https://transcript-delta.vercel.app"],  # Explicitly list the origin
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": "*",  # Allow all headers
        "expose_headers": ["Content-Disposition"],
        "supports_credentials": True,
        "max_age": 600
    }
})



# Add more detailed CORS error handling
@app.errorhandler(403)
def handle_cors_error(e):
    if 'CORS' in str(e):
        logger.error(f"CORS Error: {str(e)}")
        logger.error(f"Request Origin: {request.headers.get('Origin')}")
        logger.error(f"Request Method: {request.method}")
        logger.error(f"Request Headers: {dict(request.headers)}")
        return jsonify({
            'error': 'CORS error',
            'message': 'Origin not allowed',
            'allowed_origins': ["https://transcript-delta.vercel.app"]
        }), 403
    return {'error': str(e)}, 403

# Clear and recreate directories
for folder in [UPLOAD_FOLDER, TEMP_FOLDER, TRANSCRIPTS_FOLDER]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    # Give full permissions
    os.chmod(folder, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

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

# 3. Helper functions and utilities
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

def save_file(file_data, folder, filename, use_firebase= USE_FIREBASE):
    if use_firebase:
        return save_to_firebase(file_data, folder, filename)
    else:
        # Save locally
        if not os.path.exists(folder):
            os.makedirs(folder)
            logger.info(f"Created folder: {folder}")

        local_path = os.path.join(folder, filename)
        logger.info(f"Saving file locally to: {local_path}")

        try:
            if isinstance(file_data, bytes):
                with open(local_path, 'wb') as f:
                    f.write(file_data)
            else:
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(file_data)
                    
            logger.info(f"✅ File saved successfully at: {local_path}")
            logger.info(f"File exists check: {os.path.exists(local_path)}")
            logger.info(f"File size: {os.path.getsize(local_path)} bytes")
            return local_path
        
        except Exception as e:
            logger.error(f"❌ Error saving file: {e}")
            raise

   
# 4. Core business logic functions
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

def handle_file_uploads():
    """Handle multiple file uploads for transcription."""
    logger.info("=============================================")
    logger.info("Starting file upload handling")
    logger.info(f"Request files: {request.files}")
    logger.info(f"Request form data: {dict(request.form)}")
    logger.info(f"Firebase mode: {USE_FIREBASE}")

    temp_files = []  # Initialize temp_files list
   
    try:
        if 'files[]' not in request.files:
           logger.error("No files[] in request.files")
           logger.error(f"Request files: {request.files}")
           return jsonify({'error': 'No files selected'}), 400
       
        files = request.files.getlist('files[]')
        logger.info(f"Received {len(files)} files")

        if not files or all(file.filename == '' for file in files):
           logger.error("No files detected or empty filenames")
           return jsonify({'error': 'No files detected'}), 400 

        all_transcripts = []
        skipped_files = []
        total_files = len(files)
        processed_count = 0

        for idx, file in enumerate(files, 1):
            logger.info(f"===== Processing file {idx}/{total_files} =====")
            logger.info(f"Filename: {file.filename}")
            logger.info(f"Content type: {file.content_type}")
           
            if not allowed_file(file.filename):
                logger.error(f"File type not allowed: {file.filename}")
                skipped_files.append({
                   'name': file.filename,
                   'reason': 'Unsupported file type'
                })
                continue

            try:
                update_progress(
                   f"Processing file {idx}/{total_files}: {file.filename}", 
                   (processed_count * 100) // total_files
                )

                # Save uploaded file
                filename = secure_filename(file.filename)
                logger.info(f"Secured filename: {filename}")
               
                file_content = file.read()
                logger.info(f"File content read, size: {len(file_content)} bytes")
               
                # Log before Firebase save
                logger.info(f"Attempting to save to {'Firebase' if USE_FIREBASE else 'local'} storage")
                logger.info(f"Target folder: {FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER}")

                stored_audio_path = save_file(
                   file_content,
                   FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
                   filename
                )
                logger.info(f"File saved to: {stored_audio_path}")

                # Track temp files for cleanup
                if stored_audio_path.startswith(TEMP_FOLDER):
                   logger.info(f"Adding to temp files for cleanup: {stored_audio_path}")
                   temp_files.append(stored_audio_path)

                # Prepare for processing
                process_path = stored_audio_path
                if USE_FIREBASE:
                   temp_path = os.path.join(TEMP_FOLDER, filename)
                   logger.info(f"Firebase mode: Downloading to temp path: {temp_path}")
                   success = download_file(stored_audio_path, temp_path)
                   if not success:
                       raise Exception(f"Failed to download file from Firebase to temp location: {temp_path}")
                   process_path = temp_path
                   logger.info(f"Using temp path for processing: {process_path}")
                   temp_files.append(temp_path)

                # Transcribe
                logger.info(f"Starting transcription for: {process_path}")
                transcript_file, text = transcribe_audio(
                   process_path,
                   f"Uploaded file: {filename}"
                )
               
                if transcript_file:
                    logger.info(f"Transcription completed successfully")
                    logger.info(f"Reading transcript from: {transcript_file}")
                    
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                       transcript_content = f.read()

                    transcript_filename = os.path.basename(transcript_file)
                    logger.info(f"Transcript filename: {transcript_filename}")

                    # Save the transcript
                    if USE_FIREBASE: 
                        logger.info(f"Saving transcript to Firebase in folder: {FIREBASE_TRANSCRIPT_FOLDER}")
                        stored_transcript_path = save_file(
                            transcript_content,
                            FIREBASE_TRANSCRIPT_FOLDER,
                            transcript_filename
                        )
                        logger.info(f"Transcript saved to Firebase: {stored_transcript_path}")
                    else:
                        stored_transcript_path = os.path.join(TRANSCRIPTS_FOLDER, transcript_filename)
                        logger.info(f"Saving transcript locally to: {stored_transcript_path}")
                        with open(stored_transcript_path, 'w', encoding='utf-8') as f:
                            f.write(transcript_content)
                   
                    # Add to successful transcripts
                    all_transcripts.append({
                       'title': filename,
                       'text': text,
                       'path': stored_transcript_path,
                       'filename': transcript_filename
                    })
                   
                    # Increment counter
                    processed_count += 1
                    logger.info(f"Successfully processed file {idx}/{total_files}")
                else:
                   raise Exception("Transcription failed - no transcript file produced")

            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                logger.error(traceback.format_exc())
                skipped_files.append({
                   'name': file.filename,
                   'reason': str(e)
                })
                continue

        if not all_transcripts:
           logger.error(f"No files were successfully transcribed")
           logger.error(f"Processed count: {processed_count}")
           logger.error(f"Files attempted: {[f.filename for f in files]}")
           message = "No files were successfully transcribed"
           if skipped_files:
               message += f". {len(skipped_files)} files were skipped."
           logger.error(message)
           logger.error(f"Skipped files: {skipped_files}")
           raise Exception(message)

        update_progress("Processing complete!", 100)
        current_progress['status'] = 'complete'

        response_data = {
           'status': 'success',
           'message': 'Processing complete',
           'transcripts': all_transcripts
        }

        if skipped_files:
            response_data['skipped_files'] = skipped_files

        logger.info(f"Returning response with {len(all_transcripts)} transcripts")
        return jsonify(response_data)
   
    finally:
        logger.info("Cleaning up temporary files")
        for temp_file in temp_files:
            try:
                if temp_file and os.path.exists(temp_file):
                    if temp_file.startswith(TEMP_FOLDER):
                        logger.info(f"Deleting temp file: {temp_file}")
                        delete_file(temp_file)
            except Exception as e:
                logger.error(f"Error deleting temp file {temp_file}: {e}")

def handle_single_video():
    """Handle single YouTube video transcription."""
    audio_file = None
    transcript_file = None
    stored_transcript_path = None
    
    try:
        source_url = request.form.get('source')
        logger.info(f"Processing URL: {source_url}")
        
        if not source_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Download the audio
        audio_file, title = download_audio(source_url)
        logger.info(f"Download completed - Audio file: {audio_file}, Title: {title}")
        
        if not audio_file or not os.path.exists(audio_file):
            logger.error("Audio file not found or download failed")
            raise Exception("Audio download failed or file not found")

        logger.info(f"Audio file exists at: {audio_file}")
        
        # Save audio file to storage
        with open(audio_file, 'rb') as f:
            audio_content = f.read()  # Read content before closing file
            
        audio_filename = os.path.basename(audio_file)
        stored_audio_path = save_file(
            audio_content, 
            FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
            audio_filename
        )
        logger.info(f"Audio saved to storage at: {stored_audio_path}")
        
        # Transcribe
        transcript_file, text = transcribe_audio(
            audio_file,
            f"Video: {title}\nURL: {source_url}"
        )
        
        if not transcript_file:
            raise Exception("Transcription failed")

        logger.info(f"Transcription successful, file at: {transcript_file}")

        # Read transcript content
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript_content = f.read()
            
        transcript_filename = os.path.basename(transcript_file)
        
        if not USE_FIREBASE:
            # For local development, copy transcript to final location
            stored_transcript_path = os.path.join(TRANSCRIPTS_FOLDER, transcript_filename)
            logger.info(f"Saving transcript to final location: {stored_transcript_path}")
            
            # Write to new location instead of copying
            with open(stored_transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_content)
        else:
            stored_transcript_path = save_file(
                transcript_content,
                FIREBASE_TRANSCRIPT_FOLDER,
                transcript_filename
            )

        logger.info(f"Transcript saved to storage at: {stored_transcript_path}")
        
        update_progress("Processing complete!", 100)
        current_progress['status'] = 'complete'

        response = {
            'status': 'success',
            'message': 'Processing complete',
            'transcript': text,
            'filename': transcript_filename,
            'transcript_path': stored_transcript_path
        }
        logger.info(f"Sending response with transcript path: {stored_transcript_path}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in handle_single_video: {str(e)}")
        logger.error(traceback.format_exc())
        raise

    finally:
        # Add a small delay to ensure files are not in use
        time.sleep(0.1)

        # Clean up temporary files
        if audio_file and os.path.exists(audio_file):
            logger.info(f"Cleaning up audio file: {audio_file}")
            if audio_file.startswith(TEMP_FOLDER):
                try:
                    delete_file(audio_file)
                except Exception as e:
                    logger.error(f"Error deleting audio file: {e}")
        
        # In development mode, only clean up temporary transcript files
        if not USE_FIREBASE:
            if transcript_file and os.path.exists(transcript_file):
                if transcript_file.startswith(TEMP_FOLDER):  # Only delete if it's in temp folder
                    try:
                        logger.info(f"Cleaning up temp transcript file: {transcript_file}")
                        delete_file(transcript_file)
                    except Exception as e:
                        logger.error(f"Error deleting temp transcript file: {e}")
        else:
            # In Firebase mode, clean up all local files
            if transcript_file and os.path.exists(transcript_file):
                try:
                    logger.info(f"Cleaning up transcript file: {transcript_file}")
                    delete_file(transcript_file)
                except Exception as e:
                    logger

def handle_playlist():
    """Handle YouTube playlist transcription."""
    temp_files = []  # Track temp files for cleanup
    
    try:
        source_url = request.form.get('source')
        logger.info(f"Processing playlist URL: {source_url}")
        
        if not source_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        videos = get_playlist_videos(source_url)
        if not videos:
            return jsonify({'error': 'No videos found in playlist'}), 400

        update_progress(f"Found {len(videos)} videos in playlist", 10)
        
        all_transcripts = []
        skipped_videos = []
        
        for idx, video_url in enumerate(videos, 1):
            audio_file = None
            transcript_file = None
            
            try:
                update_progress(f"Processing video {idx}/{len(videos)}")
                audio_file, title = download_audio(video_url)
                logger.info(f"Downloaded audio for video {idx}: {title}")
                
                if not audio_file:
                    raise Exception("Audio download failed")

                # Save audio file to storage
                with open(audio_file, 'rb') as f:
                    audio_content = f.read()
                    
                audio_filename = os.path.basename(audio_file)
                stored_audio_path = save_file(
                    audio_content,
                    FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
                    audio_filename
                )
                logger.info(f"Audio saved to storage at: {stored_audio_path}")

                # Transcribe
                transcript_file, text = transcribe_audio(
                    audio_file,
                    f"Video {idx}: {title}\nURL: {video_url}"
                )
                
                if not transcript_file:
                    raise Exception("Transcription failed")

                logger.info(f"Transcription successful, file at: {transcript_file}")

                # Save transcript
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript_content = f.read()
                    
                transcript_filename = os.path.basename(transcript_file)
                
                if not USE_FIREBASE:
                    # For local development, save to transcripts folder
                    stored_transcript_path = os.path.join(TRANSCRIPTS_FOLDER, transcript_filename)
                    logger.info(f"Saving transcript to final location: {stored_transcript_path}")
                    with open(stored_transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcript_content)
                else:
                    stored_transcript_path = save_file(
                        transcript_content,
                        FIREBASE_TRANSCRIPT_FOLDER,
                        transcript_filename
                    )
                
                all_transcripts.append({
                    'title': title,
                    'text': text,
                    'path': stored_transcript_path,
                    'filename': transcript_filename
                })
                
                # Track temp files for cleanup
                if audio_file:
                    temp_files.append(audio_file)
                if transcript_file and transcript_file.startswith(TEMP_FOLDER):
                    temp_files.append(transcript_file)

            except Exception as e:
                logger.error(f"Error processing video {idx}: {e}")
                skipped_videos.append({
                    'url': video_url,
                    'reason': str(e)
                })
                continue

        if not all_transcripts:
            message = "No videos were successfully transcribed"
            if skipped_videos:
                message += f". {len(skipped_videos)} videos were skipped."
            raise Exception(message)

        logger.info("Playlist processing completed successfully")
        update_progress("Processing complete!", 100)
        current_progress['status'] = 'complete'

        response_data = {
            'status': 'success',
            'message': 'Playlist processing complete',
            'transcripts': all_transcripts
        }

        if skipped_videos:
            response_data['skipped_videos'] = skipped_videos

        return jsonify(response_data)

    finally:
        # Clean up temp files but not final transcripts
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    if temp_file.startswith(TEMP_FOLDER):
                        logger.info(f"Cleaning up temp file: {temp_file}")
                        delete_file(temp_file)
                except Exception as e:
                    logger.error(f"Error deleting temp file {temp_file}: {e}")

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


# 5. Routes (endpoints)
@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "Transcription API is running"
    })

@app.route('/api/progress')
def get_progress():
    """Get current progress status"""
    return jsonify(current_progress)

@app.route('/api/process', methods=['POST'])
def process_media():
    """Process media files for transcription."""
    logger.info("=============================================")
    logger.info("Starting process_media request")
    logger.info(f"Request Files Keys: {list(request.files.keys())}")
    logger.info(f"Request Form Data: {dict(request.form)}")

    try:
        source_type = request.form.get('type')
        logger.info(f"Source type: {source_type}")
        
        if source_type == 'file':
            if 'files[]' not in request.files:
                logger.error("files[] not in request.files")
                logger.error(f"Available keys: {list(request.files.keys())}")
                return jsonify({'error': 'No files selected'}), 400

            files = request.files.getlist('files[]')
            logger.info(f"Number of files received: {len(files)}")

            for file in files:
                logger.info(f"Processing file: {file.filename}")
                logger.info(f"File content type: {file.content_type}")
                
                # Check if file type is allowed
                if not allowed_file(file.filename):
                    logger.error(f"File type not allowed: {file.filename}")
                    return jsonify({
                        'error': f'File type not allowed for {file.filename}. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
                    }), 400

            # Continue with processing...
            return handle_file_uploads()

        elif source_type == 'video':
            return handle_single_video()
        elif source_type == 'playlist':
            return handle_playlist()
        else:
            logger.error(f"Invalid source type: {source_type}")
            return jsonify({'error': 'Invalid source type'}), 400

    except Exception as e:
        logger.error("Error in process_media:")
        logger.error(str(e))
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
@app.route('/api/download/<filename>')
def download_transcript(filename):
    """Download a transcript file"""
    try:
        logger.info(f"Download request received for file: {filename}")
        logger.info(f"Storage mode: {'Firebase' if USE_FIREBASE else 'Local'}")
        
        safe_filename = secure_filename(filename)
        if USE_FIREBASE:
            logger.info(f"Attempting to download from Firebase path: {FIREBASE_TRANSCRIPT_FOLDER}/{safe_filename}")
            temp_path = os.path.join(TEMP_FOLDER, safe_filename)
            firebase_path = f"{FIREBASE_TRANSCRIPT_FOLDER}/{safe_filename}"
            
            if download_file(firebase_path, temp_path, use_firebase=True):
                logger.info(f"File downloaded to temp path: {temp_path}")
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='text/plain'
                )
            else:
                logger.error("File not found in Firebase")
                return jsonify({'error': 'File not found in Firebase'}), 404
        else:
            safe_path = os.path.join(TRANSCRIPTS_FOLDER, safe_filename)
            logger.info(f"Looking for local file at: {os.path.abspath(safe_path)}")
            logger.info(f"Transcripts directory contents: {os.listdir(TRANSCRIPTS_FOLDER)}")
            
            if os.path.exists(safe_path):
                logger.info(f"File found, sending: {safe_path}")
                return send_file(
                    safe_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='text/plain'
                )
            else:
                logger.error(f"File not found at {safe_path}")
                return jsonify({'error': 'File not found'}), 404
                
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancel', methods=['POST'])
def cancel_transcription():
    try:
        current_progress.update({
            'status': 'idle',
            'message': '',
            'progress': 0,
            'segments': []
        })

        if not USE_FIREBASE:
            if os.path.exists(TRANSCRIPTS_FOLDER):
                for file in os.listdir(TRANSCRIPTS_FOLDER):
                    try:
                        file_path = os.path.join(TRANSCRIPTS_FOLDER, file)
                        logger.info(f"Deleting file: {file_path}")
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Error deleting file {file}: {e}")

        return jsonify({'status': 'success', 'message': 'Transcription canceled'})
    except Exception as e:
        logger.error(f"Error in cancel_transcription: {e}")
        return jsonify({'error': str(e)}), 500





# if __name__ == '__main__':
#     app.run(debug=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)