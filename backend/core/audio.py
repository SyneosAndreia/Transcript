import yt_dlp
from datetime import datetime
import os
from utils.logger import logger

class AudioProcessor:

    def __init__(self, config, progress_tracker):
        self.config = config
        self.progress = progress_tracker


        self.cookies_path = config.get('YOUTUBE_COOKIES_PATH')
        self.cookies_browser = config.get('YOUTUBE_COOKIES_BROWSER')

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
            #youtube cookies
            if self.cookies_path:
                logger.info(f"Using cookies file: {self.cookies_path}")
                ydl_opts['cookies'] = self.cookies_path
            elif self.cookies_browser:
                logger.info(f"Using cookies from browser: {self.cookies_browser}")
                ydl_opts['cookies_from_browser'] = (self.cookies_browser,)


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
        
            # List of free proxy servers (you should replace these with more reliable ones)
            proxy_list = [
                'http://45.79.158.204:44554',
                'http://165.227.71.60:80',
                'http://157.245.222.183:80'
            ]
        
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

            # Try each proxy until success
            download_success = False

            for i, proxy in enumerate(proxy_list):
                try: 
                    logger.info(f"Trying with proxy {i+1}/{len(proxy_list)}: {proxy}")
                    self.progress.update(f"Trying proxy {i+1}/{len(proxy_list)}...", 10)

                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': os.path.join(self.config['TEMP_FOLDER'], output_template),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                        }],
                        'progress_hooks': [progress_hook],
                        'verbose': True,
                        'proxy': proxy,
                        'socket_timeout': 30,
                        'retries': 2
                    }

                    #youtube cookies
                    if self.cookies_path:
                        logger.info(f"Using cookies file: {self.cookies_path}")
                        ydl_opts['cookies'] = self.cookies_path
                    elif self.cookies_browser:
                        logger.info(f"Using cookies from browser: {self.cookies_browser}")
                        ydl_opts['cookies_from_browser'] = (self.cookies_browser,)

            
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        # If we get here, download was successful
                        download_success = True
                        logger.info(f"Download successful with proxy {i+1}")
                        break
                
                except Exception as e:
                    logger.error(f"Download error: {str(e)}")
                    self.progress.update(f"Proxy {i+1} failed, trying next...", 5)
                    # Continue to next proxy if this one fails
                    continue

            if not download_success: 
                raise Exception("All proxies failed. Please try uploading the file directly instead.")
        
            # Define the output filename
            filename = os.path.join(
                self.config['TEMP_FOLDER'],
                f"audio_{timestamp}.mp3"
            )
        
            # Check if file exists and is not empty
            if not os.path.exists(filename):
                logger.error(f"Downloaded file not found: {filename}")
                files_in_dir = os.listdir(self.config['TEMP_FOLDER'])
                logger.info(f"Files in directory: {files_in_dir}")
            
                # Try to find the file with similar name pattern
                possible_files = [f for f in files_in_dir if f.startswith(f"audio_{timestamp}")]
                if possible_files:
                    filename = os.path.join(self.config['TEMP_FOLDER'], possible_files[0])
                    logger.info(f"Found alternative file: {filename}")
                else:
                    raise FileNotFoundError(f"Downloaded file not found: {filename}")
        
            file_size = os.path.getsize(filename)
            logger.info(f"Download complete: {filename} (Size: {file_size} bytes)")
        
            if file_size == 0:
                raise Exception("Downloaded file is empty")
            
            return filename, info['title']
            
        except Exception as e:
            error_message = str(e)
            if "Sign in to confirm you're not a bot" in error_message:
                error_message = "YouTube is requiring verification. Please try uploading a file directly instead of using a URL, or try a different video."
            logger.error(f"Download error: {error_message}")
            self.progress.update(f"Error downloading audio: {error_message}")
            return None, None
            




