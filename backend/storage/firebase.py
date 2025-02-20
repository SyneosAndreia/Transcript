import firebase_admin
from firebase_admin import credentials, storage
import json
import os 
from utils.logger import logger

class FirebaseStorage:
    def __init__(self, config):
        self.config = config
        self._initialize_firebase()
        
    def _initialize_firebase(self):
        try:
            if os.getenv('FIREBASE_CREDENTIALS'):
                cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
                cred = credentials.Certificate(cred_dict)
            else:
                firebase_key_path = os.path.join('firebase', 'service-account.json')
                cred = credentials.Certificate(firebase_key_path)

            firebase_admin.initialize_app(cred, {
                'storageBucket': self.config.FIREBASE_STORAGE_BUCKET
            })
            self.bucket = storage.bucket()
            logger.info("Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Firebase: {str(e)}")
            raise

    def save_file(self, file_data, folder, filename):
        """Save file to Firebase Storage"""
        blob = self.bucket.blob(f"{folder}/{filename}")
        blob.upload_from_string(file_data)
        blob.make_public()
        return blob.public_url

    def download_file(self, firebase_path, local_path):
        """Download file from Firebase to local path"""
        try:
            blob = self.bucket.blob(firebase_path)
            if not blob.exists():
                return False
            blob.download_to_filename(local_path)
            return True
        except Exception as e:
            logger.error(f"Error downloading from Firebase: {e}")
            return False

    def delete_file(self, file_path):
        """Delete file from Firebase Storage"""
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting from Firebase: {e}")
            return False