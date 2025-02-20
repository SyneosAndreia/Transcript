import os
import shutil
from utils.logger import logger

class LocalStorage:
    def __init__(self, config):
        self.config = config
        self._initialize_folders()

    def _initialize_folders(self):
        for folder in [
            self.config.UPLOAD_FOLDER,
            self.config.TEMP_FOLDER,
            self.config.TRANSCRIPTS_FOLDER
        ]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logger.info(f"Created folder: {folder}")

    def save_file(self, file_data, folder, filename):
        if not os.path.exists(folder):
            os.makedirs(folder)

        local_path = os.path.join(folder, filename)

        try: 
            if isinstance(file_data, bytes):
                with open(local_path, 'wb') as f:
                    f.write(file_data)

            else:
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(file_data)
            return local_path
        except Exception as e:
            logger.error(f"Error saving file locally: {e}")
            raise

    def download_file(self, source_path, local_path):
        try:
            shutil.copy2(source_path, local_path)
            return True
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            return False
        
    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"Error deleting local file: {e}")