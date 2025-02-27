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
    
    try:
        # Install ffmpeg with all necessary dependencies
        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run(["apt-get", "install", "-y", "ffmpeg", "libvpx7"], check=True)
        logger.info("Successfully installed ffmpeg and dependencies")
    except Exception as e:
        logger.error(f"Failed to install ffmpeg: {str(e)}")
        
        # Fallback to downloading pre-compiled binaries
        try:
            logger.info("Trying fallback method...")
            # Download ffmpeg if not exists
            if not os.path.exists("bin/ffmpeg"):
                logger.info("Downloading ffmpeg...")
                subprocess.run([
                    "curl", "-L", 
                    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
                    "-o", "ffmpeg.tar.xz"
                ])
                
                # Extract
                subprocess.run(["tar", "-xf", "ffmpeg.tar.xz"])
                
                # Find the extracted directory
                dirs = [d for d in os.listdir() if os.path.isdir(d) and d.startswith("ffmpeg")]
                if dirs:
                    # Copy ffmpeg to bin directory
                    shutil.copy(f"{dirs[0]}/ffmpeg", "bin/ffmpeg")
                    subprocess.run(["chmod", "+x", "bin/ffmpeg"])
                    
                # Cleanup
                os.remove("ffmpeg.tar.xz")
                logger.info("Fallback method successful")
        except Exception as e:
            logger.error(f"Fallback method failed: {str(e)}")
    
    # Add to PATH
    os.environ["PATH"] = os.environ["PATH"] + ":" + os.path.join(os.getcwd(), "bin")
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