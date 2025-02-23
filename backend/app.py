import os
from flask import Flask
from flask_cors import CORS
from config.settings import Config
from api.routes import api
from api.error_handlers import errors
from core.progress import ProgressTracker
from storage.firebase import FirebaseStorage
from storage.local import LocalStorage

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