"""
Camera Interface for focusd

Handles camera capture using libcamera or fallback methods.
According to specification: captures frames from CSI camera at ≤ 15 fps using libcamera.
"""

import logging
import time
import threading
import numpy as np
from typing import Optional, Callable
import subprocess
import tempfile
import os
from PIL import Image
import io


class CameraInterface:
    """Camera interface for CSI camera capture"""
    
    def __init__(self, width: int = 320, height: int = 240, fps: int = 10):
        self.width = width
        self.height = height
        self.fps = fps
        self.exposure = 1000  # microseconds
        self.gain = 0
        
        self.is_running = False
        self.latest_frame: Optional[np.ndarray] = None
        self.frame_callback: Optional[Callable[[np.ndarray], None]] = None
        
        self.logger = logging.getLogger(__name__)
        self._capture_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Try to detect available camera interface
        self.camera_method = self._detect_camera_method()
        
    def _detect_camera_method(self) -> str:
        """Detect which camera capture method to use"""
        # Check for libcamera-still
        try:
            result = subprocess.run(['libcamera-still', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info("Using libcamera for capture")
                return "libcamera"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        # Check for raspistill (legacy)
        try:
            result = subprocess.run(['raspistill', '--help'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info("Using raspistill for capture")
                return "raspistill"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        # Check for OpenCV
        try:
            import cv2
            self.logger.info("Using OpenCV for capture")
            return "opencv"
        except ImportError:
            pass
            
        self.logger.warning("No camera interface found, using dummy mode")
        return "dummy"
    
    def start(self) -> bool:
        """Start camera capture"""
        if self.is_running:
            return True
            
        try:
            self.is_running = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            self.logger.info(f"Camera started: {self.width}x{self.height} @ {self.fps} fps")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start camera: {e}")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop camera capture"""
        self.is_running = False
        
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
            
        self.logger.info("Camera stopped")
    
    def _capture_loop(self):
        """Main capture loop"""
        frame_interval = 1.0 / self.fps
        
        while self.is_running:
            start_time = time.time()
            
            try:
                frame = self._capture_frame()
                if frame is not None:
                    with self._lock:
                        self.latest_frame = frame
                    
                    # Call frame callback if set
                    if self.frame_callback:
                        try:
                            self.frame_callback(frame)
                        except Exception as e:
                            self.logger.error(f"Error in frame callback: {e}")
                            
            except Exception as e:
                self.logger.error(f"Error capturing frame: {e}")
            
            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            time.sleep(sleep_time)
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame using the detected method"""
        if self.camera_method == "libcamera":
            return self._capture_libcamera()
        elif self.camera_method == "raspistill":
            return self._capture_raspistill()
        elif self.camera_method == "opencv":
            return self._capture_opencv()
        else:
            return self._capture_dummy()
    
    def _capture_libcamera(self) -> Optional[np.ndarray]:
        """Capture frame using libcamera-still"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                cmd = [
                    'libcamera-still',
                    '-o', tmp_file.name,
                    '--width', str(self.width),
                    '--height', str(self.height),
                    '--timeout', '1',  # 1ms timeout for immediate capture
                    '--nopreview',
                    '--immediate',
                    '--shutter', str(self.exposure),
                    '--gain', str(self.gain)
                ]
                
                result = subprocess.run(cmd, capture_output=True, timeout=5)
                
                if result.returncode == 0 and os.path.exists(tmp_file.name):
                    # Load and convert image
                    image = Image.open(tmp_file.name)
                    frame = np.array(image)
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
                    
                    return frame
                else:
                    self.logger.warning(f"libcamera-still failed: {result.stderr.decode()}")
                    
        except Exception as e:
            self.logger.error(f"libcamera capture error: {e}")
            
        return None
    
    def _capture_raspistill(self) -> Optional[np.ndarray]:
        """Capture frame using raspistill"""
        try:
            cmd = [
                'raspistill',
                '-w', str(self.width),
                '-h', str(self.height),
                '-t', '1',  # 1ms timeout
                '-n',  # no preview
                '-e', 'jpg',
                '-ss', str(self.exposure),
                '-ag', str(self.gain),
                '-o', '-'  # output to stdout
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            
            if result.returncode == 0:
                # Load image from bytes
                image = Image.open(io.BytesIO(result.stdout))
                frame = np.array(image)
                return frame
            else:
                self.logger.warning(f"raspistill failed: {result.stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"raspistill capture error: {e}")
            
        return None
    
    def _capture_opencv(self) -> Optional[np.ndarray]:
        """Capture frame using OpenCV (fallback)"""
        try:
            import cv2
            
            # Initialize camera if not done yet
            if not hasattr(self, '_cv_camera'):
                self._cv_camera = cv2.VideoCapture(0)
                self._cv_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cv_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self._cv_camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            ret, frame = self._cv_camera.read()
            if ret:
                return frame
            else:
                self.logger.warning("OpenCV capture failed")
                
        except Exception as e:
            self.logger.error(f"OpenCV capture error: {e}")
            
        return None
    
    def _capture_dummy(self) -> Optional[np.ndarray]:
        """Generate dummy frame for testing"""
        # Create a synthetic test pattern
        t = time.time()
        x = np.arange(self.width)
        y = np.arange(self.height)
        X, Y = np.meshgrid(x, y)
        
        # Moving Gaussian blob
        center_x = self.width // 2 + 50 * np.sin(t * 0.5)
        center_y = self.height // 2 + 30 * np.cos(t * 0.3)
        
        frame = 100 + 100 * np.exp(
            -((X - center_x) ** 2 + (Y - center_y) ** 2) / (2 * 20 ** 2)
        )
        
        # Add some noise
        frame += np.random.normal(0, 5, frame.shape)
        
        return frame.astype(np.uint8)
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get the latest captured frame"""
        with self._lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def capture_single_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame immediately"""
        return self._capture_frame()
    
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """Set callback function to be called for each frame"""
        self.frame_callback = callback
    
    def update_settings(self, exposure: Optional[int] = None, gain: Optional[int] = None):
        """Update camera settings"""
        if exposure is not None:
            self.exposure = max(0, exposure)
        if gain is not None:
            self.gain = max(0, min(30, gain))
            
        self.logger.info(f"Camera settings updated: exposure={self.exposure}, gain={self.gain}")
    
    def get_frame_rate(self) -> float:
        """Get current frame rate"""
        return self.fps
    
    def is_connected(self) -> bool:
        """Check if camera is connected and running"""
        return self.is_running