"""
MJPEG Streaming for focusd

Provides MJPEG video streaming for debugging as specified:
- Exposes MJPEG stream of raw frames over HTTPS to avoid mixed content issues
"""

import logging
import threading
import time
from typing import Optional, Generator
import numpy as np
from io import BytesIO
from PIL import Image
import cv2


class MJPEGStreamer:
    """MJPEG streaming server for camera frames"""
    
    def __init__(self, quality: int = 85):
        self.quality = quality
        self.latest_frame: Optional[np.ndarray] = None
        self.is_running = False
        self.clients = set()
        
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        
    def start(self):
        """Start the MJPEG streamer"""
        self.is_running = True
        self.logger.info("MJPEG streamer started")
    
    def stop(self):
        """Stop the MJPEG streamer"""
        self.is_running = False
        with self._lock:
            self.clients.clear()
        self.logger.info("MJPEG streamer stopped")
    
    def update_frame(self, frame: np.ndarray):
        """Update the latest frame for streaming"""
        with self._lock:
            self.latest_frame = frame.copy()
    
    def _encode_frame(self, frame: np.ndarray) -> bytes:
        """Encode frame as JPEG bytes"""
        try:
            # Convert frame to RGB if it's grayscale
            if len(frame.shape) == 2:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            elif len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            # Convert to PIL Image and encode as JPEG
            image = Image.fromarray(frame_rgb.astype(np.uint8))
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=self.quality)
            return buffer.getvalue()
            
        except Exception as e:
            self.logger.error(f"Error encoding frame: {e}")
            return b''
    
    def generate_mjpeg_stream(self) -> Generator[bytes, None, None]:
        """Generate MJPEG stream data"""
        boundary = "frame"
        
        while self.is_running:
            with self._lock:
                frame = self.latest_frame
                
            if frame is not None:
                # Encode frame as JPEG
                jpeg_data = self._encode_frame(frame)
                
                if jpeg_data:
                    # Create MJPEG multipart response
                    yield (b'--' + boundary.encode() + b'\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n'
                           b'\r\n' + jpeg_data + b'\r\n')
            
            # Limit frame rate to prevent overwhelming clients
            time.sleep(1.0 / 30)  # Max 30 fps for streaming
    
    def get_frame_jpeg(self) -> Optional[bytes]:
        """Get current frame as JPEG bytes for single frame capture"""
        with self._lock:
            frame = self.latest_frame
            
        if frame is not None:
            return self._encode_frame(frame)
        return None
    
    def add_client(self):
        """Add a streaming client"""
        client_id = id(threading.current_thread())
        with self._lock:
            self.clients.add(client_id)
        self.logger.debug(f"MJPEG client added: {client_id}")
    
    def remove_client(self):
        """Remove a streaming client"""
        client_id = id(threading.current_thread())
        with self._lock:
            self.clients.discard(client_id)
        self.logger.debug(f"MJPEG client removed: {client_id}")
    
    def get_client_count(self) -> int:
        """Get number of active streaming clients"""
        with self._lock:
            return len(self.clients)
    
    def has_frame(self) -> bool:
        """Check if there's a frame available"""
        with self._lock:
            return self.latest_frame is not None