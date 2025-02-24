import yt_dlp
from datetime import datetime
import os
from utils.logger import logger

class AudioProcessor:

    def __init__(self, config, progress_tracker):
        self.config = config
        self.progress = progress_tracker

    def get_playlist_videos(self, url):
        """Extract video URLs from a YouTube playlist."""
        try:
            logger.info(f"Extracting videos from playlist: {url}")
            self.progress.update("Analyzing playlist...", 0)

            ydl_opts = {
                'quiet': False,  # Changed to False for more debugging
                'extract_flat': 'in_playlist',
                'force_generic_extractor': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)

                # Changed to return list of dictionaries instead of just URLs
                if 'entries' in playlist_info:
                    videos = [
                        {
                            'url': entry.get('url', ''),
                            'title': entry.get('title', f'Video {idx+1}')
                        } 
                        for idx, entry in enumerate(playlist_info['entries'])
                    ]
                    logger.info(f"Found {len(videos)} videos in playlist") 
                    return videos
                else:
                    logger.info("No playlist entries found, treating as single video")
                    return [{
                        'url': playlist_info.get('webpage_url', url),
                        'title': playlist_info.get('title', 'Unknown Video')
                    }]

        except Exception as e:
            logger.error(f"Error extracting playlist info: {str(e)}")
            self.progress.update(f"Error getting playlist: {str(e)}")
            return []

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

