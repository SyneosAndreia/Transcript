import os
import sys
print("Current file path:", __file__)
print("Current directory:", os.path.dirname(__file__))
print("Python path:", sys.path)

from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import traceback
from utils.logger import logger
from core.audio import AudioProcessor
from core.transcription import Transcriber
import time

print("Routes module is being imported!")


api = Blueprint('api', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def handle_file_uploads():
    USE_FIREBASE = current_app.config['USE_FIREBASE']
    TEMP_FOLDER = current_app.config['TEMP_FOLDER']
    FIREBASE_AUDIO_FOLDER = current_app.config['FIREBASE_AUDIO_FOLDER']
    FIREBASE_TRANSCRIPT_FOLDER = current_app.config['FIREBASE_TRANSCRIPT_FOLDER'] 
    TRANSCRIPTS_FOLDER = current_app.config['TRANSCRIPTS_FOLDER']

    # Ensure temp folder exists
    os.makedirs(TEMP_FOLDER, exist_ok=True)

    storage = current_app.storage
    transcriber = Transcriber(current_app.config, current_app.progress_tracker)
    progress_tracker = current_app.progress_tracker

    temp_files = []
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
                progress_tracker.update(
                    f"Processing file {idx}/{total_files}: {file.filename}", 
                    (processed_count * 100) // total_files
                )

                # Save uploaded file
                filename = secure_filename(file.filename)
                logger.info(f"Secured filename: {filename}")
               
                file_content = file.read()
                logger.info(f"File content read, size: {len(file_content)} bytes")

                if USE_FIREBASE:
                    # Save to Firebase
                    logger.info(f"Saving to Firebase audio folder: {FIREBASE_AUDIO_FOLDER}")
                    stored_audio_path = storage.save_file(
                        file_content,
                        FIREBASE_AUDIO_FOLDER,
                        filename
                    )
                    logger.info(f"File saved to Firebase, URL: {stored_audio_path}")
                    
                    # Download for processing using correct path format
                    firebase_path = f"{FIREBASE_AUDIO_FOLDER}/{filename}"
                    temp_path = os.path.join(TEMP_FOLDER, filename)
                    logger.info(f"Downloading from Firebase path: {firebase_path} to temp path: {temp_path}")
                    
                    success = storage.download_file(firebase_path, temp_path)
                    if not success:
                        raise Exception(f"Failed to download from Firebase path: {firebase_path}")
                    
                    process_path = temp_path
                    temp_files.append(temp_path)
                else:
                    # Local storage
                    process_path = os.path.join(TEMP_FOLDER, filename)
                    with open(process_path, 'wb') as f:
                        f.write(file_content)
                    temp_files.append(process_path)

                # Transcribe
                logger.info(f"Starting transcription for: {process_path}")
                transcript_file, text = transcriber.transcribe_audio(
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
                        logger.info(f"Saving transcript to Firebase folder: {FIREBASE_TRANSCRIPT_FOLDER}")
                        stored_transcript_path = storage.save_file(
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

        progress_tracker.update(
            message="Processing complete!",
            progress=100
        )

        # Set completion status
        progress_tracker.current_progress['status'] = 'complete'

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
                    logger.info(f"Deleting temp file: {temp_file}")
                    os.remove(temp_file)
            except Exception as e:
                logger.error(f"Error deleting temp file {temp_file}: {e}")

def handle_single_video(source_url):
    """Handle single video URL processing"""
    audio_file = None
    transcript_file = None
    stored_transcript_path = None
    progress_tracker = current_app.progress_tracker

    try: 
        logger.info(f"Processing URL: {source_url}")

        if not source_url:
            return jsonify({'error': 'No URL provided' }), 400
        
        #Download using audio processor
        audio_processor = AudioProcessor(current_app.config, current_app.progress_tracker)
        audio_file, title = audio_processor.download_audio(source_url)
        logger.info(f"Download completed - Audio file: {audio_file}, Title: {title}")
        
        if not audio_file:
            raise Exception("Audio download failed or file not found")

        logger.info(f"Audio file exists at: {audio_file}")

         # Save audio file to storage
        USE_FIREBASE = current_app.config['USE_FIREBASE']
        TEMP_FOLDER = current_app.config['TEMP_FOLDER']
        FIREBASE_AUDIO_FOLDER = current_app.config['FIREBASE_AUDIO_FOLDER']
        FIREBASE_TRANSCRIPT_FOLDER = current_app.config['FIREBASE_TRANSCRIPT_FOLDER']
        TRANSCRIPTS_FOLDER = current_app.config['TRANSCRIPTS_FOLDER']
        
        with open(audio_file, 'rb') as f:
            audio_content = f.read()

        audio_filename = os.path.basename(audio_file)
        stored_audio_path = current_app.storage.save_file(
            audio_content, 
            FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
            audio_filename
        )
        logger.info(f"Audio saved to storage at: {stored_audio_path}")
        
        # Transcribe using Transcriber
        transcriber = Transcriber(current_app.config, progress_tracker)
        transcript_file, text = transcriber.transcribe_audio(
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
            
            with open(stored_transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_content)
        else:
            stored_transcript_path = current_app.storage.save_file(
                transcript_content,
                FIREBASE_TRANSCRIPT_FOLDER,
                transcript_filename
            )

        logger.info(f"Transcript saved to storage at: {stored_transcript_path}")
        
        # Update progress and set completion status
        progress_tracker.update(
            message="Processing complete!",
            progress=100,
            status='complete'
        )

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
        progress_tracker.update(
            message=f"Error: {str(e)}",
            status='error'
        )
        return jsonify({'error': str(e)}), 500

    finally:
        # Add a small delay to ensure files are not in use
        time.sleep(0.1)

        # Clean up temporary files
        if audio_file and os.path.exists(audio_file):
            logger.info(f"Cleaning up audio file: {audio_file}")
            if audio_file.startswith(TEMP_FOLDER):
                try:
                    current_app.storage.delete_file(audio_file)
                except Exception as e:
                    logger.error(f"Error deleting audio file: {e}")
        
        # In development mode, only clean up temporary transcript files
        if not USE_FIREBASE:
            if transcript_file and os.path.exists(transcript_file):
                if transcript_file.startswith(TEMP_FOLDER):
                    try:
                        logger.info(f"Cleaning up temp transcript file: {transcript_file}")
                        current_app.storage.delete_file(transcript_file)
                    except Exception as e:
                        logger.error(f"Error deleting temp transcript file: {e}")
        else:
            # In Firebase mode, clean up all local files
            if transcript_file and os.path.exists(transcript_file):
                try:
                    logger.info(f"Cleaning up transcript file: {transcript_file}")
                    current_app.storage.delete_file(transcript_file)
                except Exception as e:
                    logger.error(f"Error deleting transcript file: {e}")

def handle_playlist(source_url): 
    """Handle YouTube playlist transcription."""
    temp_files = []
    progress_tracker = current_app.progress_tracker
    
    try:
        logger.info(f"Processing playlist URL: {source_url}")
        
        if not source_url:
            return jsonify({'error': 'No URL provided'}), 400

        # Get config values
        USE_FIREBASE = current_app.config['USE_FIREBASE']
        TEMP_FOLDER = current_app.config['TEMP_FOLDER']
        FIREBASE_AUDIO_FOLDER = current_app.config['FIREBASE_AUDIO_FOLDER']
        FIREBASE_TRANSCRIPT_FOLDER = current_app.config['FIREBASE_TRANSCRIPT_FOLDER']
        TRANSCRIPTS_FOLDER = current_app.config['TRANSCRIPTS_FOLDER']
        
        # Initialize processors
        audio_processor = AudioProcessor(current_app.config, progress_tracker)
        transcriber = Transcriber(current_app.config, progress_tracker)
        
        # Get videos from playlist using passed source_url
        videos = audio_processor.get_playlist_videos(source_url)
        if not videos:
            return jsonify({'error': 'No videos found in playlist'}), 400

        progress_tracker.update(f"Found {len(videos)} videos in playlist", 10)
        
        all_transcripts = []
        skipped_videos = []
        
        for idx, video_info in enumerate(videos, 1):
            audio_file = None
            transcript_file = None
            
            try:
                progress_tracker.update(f"Processing video {idx}/{len(videos)}: {video_info['title']}")
                
                # Download audio using AudioProcessor
                audio_file, title = audio_processor.download_audio(video_info['url'])
                logger.info(f"Downloaded audio for video {idx}: {title}")
                
                if not audio_file:
                    raise Exception("Audio download failed")

                # Save audio file to storage
                with open(audio_file, 'rb') as f:
                    audio_content = f.read()
                    
                audio_filename = os.path.basename(audio_file)
                stored_audio_path = current_app.storage.save_file(
                    audio_content,
                    FIREBASE_AUDIO_FOLDER if USE_FIREBASE else TEMP_FOLDER,
                    audio_filename
                )
                logger.info(f"Audio saved to storage at: {stored_audio_path}")

                # Transcribe using Transcriber
                transcript_file, text = transcriber.transcribe_audio(
                    audio_file,
                    f"Video {idx}: {title}\nURL: {video_info['url']}"
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
                    stored_transcript_path = current_app.storage.save_file(
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
                    'url': video_info['url'],
                    'title': video_info['title'],
                    'reason': str(e)
                })
                continue

        if not all_transcripts:
            message = "No videos were successfully transcribed"
            if skipped_videos:
                message += f". {len(skipped_videos)} videos were skipped."
            raise Exception(message)

        logger.info("Playlist processing completed successfully")
        progress_tracker.update(
            message="Processing complete!",
            progress=100,
            status='complete'
        )

        response_data = {
            'status': 'success',
            'message': 'Playlist processing complete',
            'transcripts': all_transcripts
        }

        if skipped_videos:
            response_data['skipped_videos'] = skipped_videos

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in handle_playlist: {str(e)}")
        logger.error(traceback.format_exc())
        progress_tracker.update(
            message=f"Error: {str(e)}",
            status='error'
        )
        return jsonify({'error': str(e)}), 500

    finally:
        # Add a small delay to ensure files are not in use
        time.sleep(0.1)
        
        # Clean up temp files
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    if temp_file.startswith(TEMP_FOLDER):
                        logger.info(f"Cleaning up temp file: {temp_file}")
                        current_app.storage.delete_file(temp_file)
                except Exception as e:
                    logger.error(f"Error deleting temp file {temp_file}: {e}")

@api.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@api.route('/process', methods=['POST'])
def process_media():
    """Process media files for transcription."""
    logger.info("=============================================")
    logger.info("Starting process_media request")
    logger.info(f"Request Files Keys: {list(request.files.keys())}")
    logger.info(f"Request Form Data: {dict(request.form)}")

    try:
        # Check if type exists in form
        if 'type' not in request.form:
            logger.error("No type in request.form")
            return jsonify({'error': 'Source type not specified'}), 400

        # Get form data first
        source_type = request.form.get('type')
        source_url = request.form.get('source')
        
        # Then log it
        logger.info(f"Source type: {source_type}")
        logger.info(f"Source URL: {source_url}")
        
        if source_type == 'file':
            logger.info("Processing file upload...")
            if 'files[]' not in request.files:
                logger.error("files[] not in request.files")
                logger.error(f"Available keys: {list(request.files.keys())}")
                return jsonify({'error': 'No files selected'}), 400

            files = request.files.getlist('files[]')
            logger.info(f"Number of files received: {len(files)}")

            # Check if files list is empty
            if not files or len(files) == 0:
                logger.error("Empty files list")
                return jsonify({'error': 'No files received'}), 400

            for file in files:
                if not file.filename:
                    logger.error("Empty filename received")
                    return jsonify({'error': 'Empty filename'}), 400

                logger.info(f"Processing file: {file.filename}")
                logger.info(f"File content type: {file.content_type}")
                
                if not allowed_file(file.filename):
                    logger.error(f"File type not allowed: {file.filename}")
                    return jsonify({
                        'error': f'File type not allowed for {file.filename}. Allowed types: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}'
                    }), 400

            logger.info("All files validated, calling handle_file_uploads()")
            response = handle_file_uploads()
            logger.info("handle_file_uploads() completed")
            return response

        elif source_type == 'video':
            logger.info("Processing video...")
            if not source_url:
                return jsonify({'error': 'No URL provided'}), 400
            response = handle_single_video(source_url)  # Pass the URL here
            logger.info("Video processing completed")
            return response

        elif source_type == 'playlist':
            logger.info("Processing playlist...")
            if not source_url:
                return jsonify({'error': 'No URL provided'}), 400
            response = handle_playlist(source_url)  # Passing the URL is correct
            logger.info("Playlist processing completed")
            return response

        else:
            logger.error(f"Invalid source type: {source_type}")
            return jsonify({'error': f'Invalid source type: {source_type}'}), 400

    except Exception as e:
        logger.error("Error in process_media:")
        logger.error(str(e))
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@api.route('/progress')
def get_progress():
    """Get current progress status"""
    return jsonify(current_app.progress_tracker.get_progress())

@api.route('/download/<filename>')
def download_transcript(filename):
    """Download a transcript file"""
    try:
        logger.info(f"Download request received for file: {filename}")
        USE_FIREBASE = current_app.config['USE_FIREBASE']
        logger.info(f"Storage mode: {'Firebase' if USE_FIREBASE else 'Local'}")
        
        safe_filename = secure_filename(filename)
        if USE_FIREBASE:
            logger.info(f"Attempting to download from Firebase path: {current_app.config['FIREBASE_TRANSCRIPT_FOLDER']}/{safe_filename}")
            temp_path = os.path.join(current_app.config['TEMP_FOLDER'], safe_filename)
            firebase_path = f"{current_app.config['FIREBASE_TRANSCRIPT_FOLDER']}/{safe_filename}"
            
            if current_app.storage.download_file(firebase_path, temp_path):
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
            safe_path = os.path.join(current_app.config['TRANSCRIPTS_FOLDER'], safe_filename)
            logger.info(f"Looking for local file at: {os.path.abspath(safe_path)}")
            logger.info(f"Transcripts directory contents: {os.listdir(current_app.config['TRANSCRIPTS_FOLDER'])}")
            
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
    

@api.route('/cancel', methods=['POST'])
def cancel_transcription():
    USE_FIREBASE = current_app.config['USE_FIREBASE']
    TRANSCRIPTS_FOLDER = current_app.config['TRANSCRIPTS_FOLDER']
    progress_tracker = current_app.progress_tracker

    try:
        # Reset progress tracker using its existing reset method
        progress_tracker.reset()

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