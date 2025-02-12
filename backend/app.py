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

app = Flask(__name__)
CORS(app, resources ={
        r"/api/*": {
        "origins": ["http://localhost:5173"], 
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

# Configuration
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp_audio'
TRANSCRIPTS_FOLDER = 'transcripts'
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'm4a'}

# Clear and recreate directories
for folder in [UPLOAD_FOLDER, TEMP_FOLDER, TRANSCRIPTS_FOLDER]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    # Give full permissions
    os.chmod(folder, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

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

        # Create a timestamp-based filename to avoid special characters
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_template = f"audio_{timestamp}.%(ext)s"  # Remove the path join here

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_path, output_template),  # Add the path here instead
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            'progress_hooks': [progress_hook],
            'verbose': True,
            'no_warnings': False
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
                # List all files in directory
                files = os.listdir(output_path)
                print(f"Files in directory: {files}")
                raise FileNotFoundError(f"Downloaded file not found: {filename}")
                
            file_size = os.path.getsize(filename)
            print(f"Download complete: {filename} (Size: {file_size} bytes)")
            
            if file_size == 0:
                raise Exception("Downloaded file is empty")
                
            return filename, title
            
    except Exception as e:
        print(f"Download error: {str(e)}")
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
            for segment in current_progress['segments']:
                f.write(f"[{segment['start']} --> {segment['end']}] {segment['text']}\n")

            f.write("\n\nFull Transcript:\n")
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
        
        # Default save location is the TRANSCRIPTS_FOLDER
        save_location = request.form.get('save_location', TRANSCRIPTS_FOLDER)
        os.makedirs(save_location, exist_ok=True)
        
        if source_type == 'video':
            source_url = request.form.get('source')
            print(f"Processing URL: {source_url}")
            
            if not source_url:
                return jsonify({'error': 'No URL provided'}), 400
            
            # Download the audio
            audio_file, title = download_audio(source_url)
            
            # Check if file exists and has content
            if audio_file and os.path.exists(audio_file):
                print(f"Audio file exists at: {audio_file}")
                file_size = os.path.getsize(audio_file)
                print(f"File size: {file_size} bytes")
                
                # Try to transcribe
                transcript_file, text = transcribe_audio(
                    audio_file,
                    f"Video: {title}\nURL: {source_url}"
                )
                
                if transcript_file:
                    # Clean up only after successful transcription
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                        print(f"Cleaned up audio file: {audio_file}")
                    
                    print("Process completed successfully")
                    update_progress("Processing complete!", 100)
                    current_progress['status'] = 'complete'
                    
                    # Get the filename for download
                    transcript_filename = os.path.basename(transcript_file)
                    
                    # If custom save location is provided, copy the file there
                    if save_location != TRANSCRIPTS_FOLDER:
                        custom_path = os.path.join(save_location, transcript_filename)
                        shutil.copy2(transcript_file, custom_path)
                        print(f"Saved transcript to custom location: {custom_path}")
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Processing complete',
                        'transcript': text,
                        'filename': transcript_filename,
                        'filepath': os.path.join(save_location, transcript_filename)
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
                    transcript_file, text = transcribe_audio(
                        audio_file, 
                        f"Video {idx}: {title}\nURL: {video_url}"
                    )
                    
                    if transcript_file:
                        all_transcripts.append({
                            'title': title,
                            'text': text,
                            'filename': os.path.basename(transcript_file)
                        })
                    
                    # Clean up audio file
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
            
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
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            print(f"File saved to: {filepath}")
            
            transcript_file, text = transcribe_audio(filepath, f"Uploaded file: {filename}")
            
            if transcript_file:
                transcript_filename = os.path.basename(transcript_file)
                
                # If custom save location is provided, copy the file there
                if save_location != TRANSCRIPTS_FOLDER:
                    custom_path = os.path.join(save_location, transcript_filename)
                    shutil.copy2(transcript_file, custom_path)
                    print(f"Saved transcript to custom location: {custom_path}")
                
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Processing complete',
                    'transcript': text,
                    'filename': transcript_filename,
                    'filepath': os.path.join(save_location, transcript_filename)
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
        # Make sure we only allow downloading from the transcripts folder for security
        safe_path = os.path.join(TRANSCRIPTS_FOLDER, secure_filename(filename))
        if os.path.exists(safe_path):
            return send_file(
                safe_path,
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True)