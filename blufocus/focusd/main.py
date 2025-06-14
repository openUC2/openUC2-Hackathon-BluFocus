"""
Main focusd service

Integrates all components according to specification:
- Captures frames from CSI camera at ≤ 15 fps using libcamera
- Applies user-defined exposure & gain on each capture  
- Calls FocusMetric.compute(frame) and obtains single float per frame
- Publishes metric to CAN (event-push every frame and on-demand pull)
- Exposes MJPEG stream of raw frames on http://<pi>:8080/stream.mjpg
- Exposes REST API via FastAPI
- Persists settings in /etc/focusd/config.yaml; loads on startup
"""

import logging
import logging.handlers
import signal
import sys
import time
import threading
import asyncio
from typing import Optional
import uvicorn

from focusd.config import ConfigManager
from focusd.camera import CameraInterface  
from focusd.can_interface import CANInterface, setup_can_interface
from focusd.mjpeg_streamer import MJPEGStreamer
from algorithms.focus_algorithm import FocusMetric, FocusConfig
from api.main import FocusdAPI


class FocusdService:
    """Main focusd service orchestrator"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.camera: Optional[CameraInterface] = None
        self.can_interface: Optional[CANInterface] = None  
        self.mjpeg_streamer: Optional[MJPEGStreamer] = None
        self.focus_metric: Optional[FocusMetric] = None
        self.api: Optional[FocusdAPI] = None
        
        self.is_running = False
        self._shutdown_event = threading.Event()
        
        # Performance tracking
        self.frame_count = 0
        self.start_time = time.time()
        self.last_performance_log = time.time()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.system.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.handlers.SysLogHandler(address='/dev/log') if sys.platform.startswith('linux') else logging.StreamHandler()
            ]
        )
    
    def start(self) -> bool:
        """Start all focusd components"""
        try:
            self.logger.info("Starting focusd autofocus service...")
            
            # Setup CAN interface first
            if not self._setup_can():
                return False
            
            # Initialize focus algorithm
            self._setup_focus_algorithm()
            
            # Initialize camera
            if not self._setup_camera():
                return False
            
            # Initialize MJPEG streamer
            if not self._setup_mjpeg_streamer():
                return False
            
            # Initialize API
            if not self._setup_api():
                return False
            
            self.is_running = True
            
            # Setup signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            self.logger.info("focusd service started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start focusd service: {e}")
            self.stop()
            return False
    
    def _setup_can(self) -> bool:
        """Setup CAN interface"""
        try:
            # Setup CAN interface at system level
            if not setup_can_interface(self.config.can.interface, self.config.can.bitrate):
                self.logger.warning("Failed to setup CAN interface, continuing without CAN")
                return True  # Don't fail startup due to CAN issues
            
            # Initialize CAN interface
            self.can_interface = CANInterface(
                interface=self.config.can.interface,
                bitrate=self.config.can.bitrate,
                tx_id=self.config.can.arbitration_id_tx,
                rx_id=self.config.can.arbitration_id_rx
            )
            
            if self.can_interface.start():
                self.can_interface.set_push_mode(self.config.can.enable_push_mode)
                self.can_interface.set_pull_mode(self.config.can.enable_pull_mode)
                self.logger.info("CAN interface initialized")
            else:
                self.logger.warning("CAN interface failed to start, continuing without CAN")
                self.can_interface = None
                
            return True
            
        except Exception as e:
            self.logger.warning(f"CAN setup failed: {e}, continuing without CAN")
            self.can_interface = None
            return True
    
    def _setup_focus_algorithm(self):
        """Setup focus algorithm"""
        focus_config = FocusConfig(
            gaussian_sigma=self.config.focus_algorithm.gaussian_sigma,
            background_threshold=self.config.focus_algorithm.background_threshold,
            crop_radius=self.config.focus_algorithm.crop_radius,
            enable_gaussian_blur=self.config.focus_algorithm.enable_gaussian_blur
        )
        
        self.focus_metric = FocusMetric(focus_config)
        self.logger.info("Focus algorithm initialized")
    
    def _setup_camera(self) -> bool:
        """Setup camera interface"""
        try:
            self.camera = CameraInterface(
                width=self.config.camera.width,
                height=self.config.camera.height,
                fps=self.config.camera.fps
            )
            
            self.camera.update_settings(
                exposure=self.config.camera.exposure,
                gain=self.config.camera.gain
            )
            
            # Set frame callback for processing
            self.camera.set_frame_callback(self._process_frame)
            
            if self.camera.start():
                self.logger.info("Camera interface initialized")
                return True
            else:
                self.logger.error("Failed to start camera")
                return False
                
        except Exception as e:
            self.logger.error(f"Camera setup failed: {e}")
            return False
    
    def _setup_mjpeg_streamer(self) -> bool:
        """Setup MJPEG streamer"""
        try:
            self.mjpeg_streamer = MJPEGStreamer(quality=85)
            self.mjpeg_streamer.start()
            self.logger.info("MJPEG streamer initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"MJPEG streamer setup failed: {e}")
            return False
    
    def _setup_api(self) -> bool:
        """Setup FastAPI"""
        try:
            self.api = FocusdAPI(self.config_manager, self.mjpeg_streamer)
            self.logger.info("FastAPI initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"API setup failed: {e}")
            return False
    
    def _process_frame(self, frame):
        """Process each camera frame"""
        try:
            processing_start = time.time()
            
            # Update MJPEG streamer
            if self.mjpeg_streamer:
                self.mjpeg_streamer.update_frame(frame)
            
            # Compute focus metric
            if self.focus_metric:
                focus_data = self.focus_metric.compute(frame)
                
                # Update API with latest focus data
                if self.api:
                    self.api.update_focus_data(focus_data)
                
                # Publish to CAN bus
                if self.can_interface and self.can_interface.push_mode_enabled:
                    self.can_interface.publish_focus_value(focus_data["focus"])
                    # Also update for pull mode
                    self.can_interface.update_latest_focus(focus_data["focus"])
            
            # Performance tracking
            processing_time = time.time() - processing_start
            self.frame_count += 1
            
            # Check CAN latency requirement (≤ 40 ms)
            if processing_time > 0.040:
                self.logger.warning(f"Frame processing took {processing_time*1000:.1f}ms (>40ms target)")
            
            # Log performance stats periodically
            current_time = time.time()
            if current_time - self.last_performance_log > 30:  # Every 30 seconds
                self._log_performance_stats()
                self.last_performance_log = current_time
                
        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")
    
    def _log_performance_stats(self):
        """Log performance statistics"""
        uptime = time.time() - self.start_time
        fps = self.frame_count / uptime if uptime > 0 else 0
        
        self.logger.info(f"Performance: {fps:.1f} fps, {self.frame_count} frames processed in {uptime:.1f}s")
        
        # Reset counters
        self.frame_count = 0
        self.start_time = time.time()
    
    def run(self):
        """Run the service with FastAPI server"""
        if not self.start():
            sys.exit(1)
        
        try:
            # Run FastAPI server in the main thread
            config = self.config_manager.get_config()
            uvicorn.run(
                self.api.app,
                host=config.api.host,
                port=config.api.port,
                log_level="info",
                access_log=True
            )
            
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop all components"""
        self.logger.info("Stopping focusd service...")
        self.is_running = False
        
        # Stop components in reverse order
        if self.api:
            # FastAPI stops when main thread exits
            pass
            
        if self.mjpeg_streamer:
            self.mjpeg_streamer.stop()
            
        if self.camera:
            self.camera.stop()
            
        if self.can_interface:
            self.can_interface.stop()
            
        self.logger.info("focusd service stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="focusd - Autofocus System Service")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Create and run service
    service = FocusdService(config_path=args.config)
    
    # Override log level if specified
    if args.log_level:
        service.config.system.log_level = args.log_level
        service._setup_logging()
    
    service.run()


if __name__ == "__main__":
    main()