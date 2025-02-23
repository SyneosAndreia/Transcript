from utils.logger import logger

class ProgressTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.current_progress = {
            'status': 'idle',
            'message': '',
            'progress': 0,
            'current_text': '',
            'segments': []
        }

    def update(self, message, progress=None, segment=None, **kwargs):
        self.current_progress['message'] = message
        if progress is not None:
            self.current_progress['progress'] = progress
        if segment is not None:
            self.current_progress['segments'].append(segment)

        # Log any unexpected keyword arguments
        if kwargs:
            logger.warning(f"Unexpected arguments passed to update: {kwargs}")

    def get_progress(self):
        return self.current_progress