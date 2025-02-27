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

# Set up ffmpeg if needed
def setup_ffmpeg():
    logger.info("Setting up ffmpeg...")
    # Create bin directory
    os.makedirs("bin", exist_ok=True)
    
    # Download ffmpeg if not exists
    if not os.path.exists("bin/ffmpeg"):
        print("Downloading ffmpeg...")
        
        if os.name == 'nt':  # Windows
            # Windows download
            subprocess.run([
                "curl", "-L", 
                "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-essentials_build.zip",
                "-o", "ffmpeg.zip"
            ])
            import zipfile
            with zipfile.ZipFile("ffmpeg.zip", 'r') as zip_ref:
                zip_ref.extractall(".")
            # Copy the ffmpeg.exe to bin folder
            shutil.copy("ffmpeg-5.1.2-essentials_build/bin/ffmpeg.exe", "bin/ffmpeg.exe")
            os.remove("ffmpeg.zip")
        else:  # Linux/Mac
            subprocess.run([
                "curl", "-L", 
                "https://github.com/eugeneware/ffmpeg-static/releases/download/b4.4.0/linux-x64",
                "-o", "bin/ffmpeg"
            ])
            # Make executable on Unix systems
            subprocess.run(["chmod", "+x", "bin/ffmpeg"])
    
    # Add to PATH
    if os.name == 'nt':  # Windows
        ffmpeg_path = os.path.join(os.getcwd(), "bin")
    else:  # Linux/Mac
        ffmpeg_path = os.path.join(os.getcwd(), "bin")
    
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + ffmpeg_path
    logger.info(f"ffmpeg setup complete, PATH updated: {os.environ['PATH']}")

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
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)