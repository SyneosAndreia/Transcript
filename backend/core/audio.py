import yt_dlp
from datetime import datetime
import os
from utils.logger import logger

class AudioProcessor:

    def __init__(self, config, progress_tracker):
        self.config = config
        self.progress = progress_tracker

    def download_audio(self, url ):
        try: 
            logger.info(f"Starting download from URL: {url}")
            self.progress.update("Starting download...", 0)
            
            if not url:
                raise ValueError("No URL provided")

            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        percent = float(d['_percent_str'].replace('%', ''))
                        self.progress.update(
                            f"Downloading: {d['_percent_str']} at {d.get('_speed_str', 'N/A')}", 
                            int(percent)
                        )
                    except:
                        self.progress.update(f"Downloading... {d.get('_speed_str', 'N/A')}")
                elif d['status'] == 'finished':
                    self.progress.update("Download complete, processing audio...", 100)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_template = f"audio_{timestamp}.%(ext)s"

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.config['TEMP_FOLDER'], output_template),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
                'progress_hooks': [progress_hook],
                'verbose': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = os.path.join(
                    self.config['TEMP_FOLDER'],
                    f"audio_{timestamp}.mp3"
                )
                return filename, info['title']
                
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            self.progress.update(f"Error downloading audio: {str(e)}")
            return None, None

