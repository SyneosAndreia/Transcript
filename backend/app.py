import os
from flask import Flask
from flask_cors import CORS
from config.settings import Config
from api.routes import api
from api.error_handlers import errors
from core.progress import ProgressTracker
from storage.firebase import FirebaseStorage
from storage.local import LocalStorage


import subprocess
import sys
import shutil

import logging
logger = logging.getLogger(__name__)

# Set up ffmpeg
def setup_ffmpeg():
    logger.info("Setting up ffmpeg...")
    # Create bin directory
    os.makedirs("bin", exist_ok=True)
    
    # Skip apt-get and go straight to downloading static build
    try:
        logger.info("Downloading static ffmpeg build...")
        # Use a fully static build with all dependencies included
        subprocess.run([
            "curl", "-L", 
            "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
            "-o", "ffmpeg.tar.xz"
        ], check=True)
        
        # Extract
        logger.info("Extracting ffmpeg...")
        subprocess.run(["tar", "-xf", "ffmpeg.tar.xz"], check=True)
        
        # Find the extracted directory
        dirs = [d for d in os.listdir() if os.path.isdir(d) and d.startswith("ffmpeg")]
        if dirs:
            logger.info(f"Found ffmpeg directory: {dirs[0]}")
            # Copy ffmpeg to bin directory
            shutil.copy(f"{dirs[0]}/ffmpeg", "bin/ffmpeg")
            subprocess.run(["chmod", "+x", "bin/ffmpeg"], check=True)
            logger.info("Copied ffmpeg to bin directory")
        else:
            logger.error("No ffmpeg directory found after extraction")
            
        # Cleanup
        os.remove("ffmpeg.tar.xz")
        
        # Verify installation
        if os.path.exists("bin/ffmpeg"):
            logger.info("Static ffmpeg installed successfully")
        else:
            logger.error("bin/ffmpeg does not exist after installation")
    except Exception as e:
        logger.error(f"Static ffmpeg installation failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Add bin to PATH but prioritize it FIRST
    bin_path = os.path.join(os.getcwd(), "bin")
    os.environ["PATH"] = f"{bin_path}:{os.environ['PATH']}"
    logger.info(f"ffmpeg setup complete, PATH updated: {os.environ['PATH']}")
    
    # Test ffmpeg
    try:
        test_cmd = ["which", "ffmpeg"]
        result = subprocess.run(test_cmd, capture_output=True, text=True)
        logger.info(f"ffmpeg location: {result.stdout.strip()}")
    except Exception as e:
        logger.error(f"Failed to locate ffmpeg: {str(e)}")
setup_ffmpeg()



def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Initialize CORS
    CORS(app, resources={
        r"/*": {
            "origins": config.ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": "*",
            "expose_headers": ["Content-Disposition"],
            "supports_credentials": True,
            "max_age": 600
        }
    })

    # Initialize components
    progress_tracker = ProgressTracker()
    storage = FirebaseStorage(config) if config.USE_FIREBASE else LocalStorage(config)
    
    # IMPORTANT: Attach components to the app context
    app.progress_tracker = progress_tracker
    app.storage = storage


    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(errors)


    # In your app configuration
    app.config['YOUTUBE_COOKIES_PATH'] = os.environ.get('YOUTUBE_COOKIES_PATH')
    app.config['YOUTUBE_COOKIES_BROWSER'] = os.environ.get('YOUTUBE_COOKIES_BROWSER', 'chrome')

    # If using environment variable to store cookies content
    if 'YOUTUBE_COOKIES_CONTENT' in os.environ:
        cookies_content = os.environ.get('YOUTUBE_COOKIES_CONTENT')
        cookies_path = os.path.join(app.config['TEMP_FOLDER'], 'youtube_cookies.txt')
    
        # Make sure TEMP_FOLDER exists
        os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
    
        with open(cookies_path, 'w') as f:
            f.write(cookies_content)
    
        app.config['YOUTUBE_COOKIES_PATH'] = cookies_path       
    
    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)