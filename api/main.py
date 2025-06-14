"""
FastAPI REST API for focusd

Implements the REST API specification from section 7:
- GET /status - health, version, uptime
- GET /config - return current config YAML
- POST /config - update config; body = partial YAML  
- POST /capture - grab single frame, return JPEG
- GET /focus - latest focus value JSON
- GET /stream - stream mjpeg data
"""

import logging
import time
import yaml
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from focusd.config import ConfigManager, FocusdConfig
from focusd.mjpeg_streamer import MJPEGStreamer


class ConfigUpdate(BaseModel):
    """Model for configuration updates"""
    camera: Optional[Dict[str, Any]] = None
    focus_algorithm: Optional[Dict[str, Any]] = None
    can: Optional[Dict[str, Any]] = None
    api: Optional[Dict[str, Any]] = None
    system: Optional[Dict[str, Any]] = None


class FocusdAPI:
    """FastAPI application for focusd"""
    
    def __init__(self, config_manager: ConfigManager, mjpeg_streamer: MJPEGStreamer):
        self.config_manager = config_manager
        self.mjpeg_streamer = mjpeg_streamer
        self.start_time = time.time()
        self.latest_focus_data: Dict[str, Any] = {"t": 0, "focus": 0.0}
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="focusd API",
            description="Autofocus System REST API",
            version="1.0.0",
            docs_url="/docs" if config_manager.get_config().api.enable_docs else None
        )
        
        # Add CORS middleware
        if config_manager.get_config().api.cors_enabled:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/status")
        async def get_status():
            """Get system health, version, and uptime"""
            uptime = time.time() - self.start_time
            
            return {
                "status": "running",
                "version": "1.0.0",
                "uptime_seconds": uptime,
                "uptime_human": self._format_uptime(uptime),
                "mjpeg_clients": self.mjpeg_streamer.get_client_count(),
                "has_camera_frame": self.mjpeg_streamer.has_frame(),
                "timestamp": time.time()
            }
        
        @self.app.get("/config")
        async def get_config():
            """Return current configuration as YAML"""
            try:
                config_dict = self.config_manager.to_dict()
                yaml_content = yaml.dump(config_dict, default_flow_style=False, indent=2)
                
                return Response(
                    content=yaml_content,
                    media_type="application/x-yaml",
                    headers={"Content-Disposition": "inline; filename=config.yaml"}
                )
            except Exception as e:
                self.logger.error(f"Error getting config: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/config")
        async def update_config(config_update: ConfigUpdate, background_tasks: BackgroundTasks):
            """Update configuration with partial YAML data"""
            try:
                # Convert Pydantic model to dict, excluding None values
                updates = config_update.dict(exclude_none=True)
                
                if not updates:
                    raise HTTPException(status_code=400, detail="No configuration updates provided")
                
                # Update configuration
                success = self.config_manager.update_config(updates)
                
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save configuration")
                
                # Validate updated configuration
                is_valid, errors = self.config_manager.validate_config()
                if not is_valid:
                    self.logger.warning(f"Configuration validation warnings: {errors}")
                
                # Schedule configuration reload in background
                background_tasks.add_task(self._reload_config)
                
                return {
                    "status": "success",
                    "message": "Configuration updated successfully",
                    "warnings": errors if not is_valid else [],
                    "timestamp": time.time()
                }
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating config: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/capture")
        async def capture_frame():
            """Capture single frame and return as JPEG"""
            try:
                jpeg_data = self.mjpeg_streamer.get_frame_jpeg()
                
                if jpeg_data is None:
                    raise HTTPException(status_code=503, detail="No frame available")
                
                return Response(
                    content=jpeg_data,
                    media_type="image/jpeg",
                    headers={"Content-Disposition": "inline; filename=capture.jpg"}
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error capturing frame: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/focus")
        async def get_focus():
            """Get latest focus value as JSON"""
            return self.latest_focus_data
        
        @self.app.get("/stream")
        async def get_mjpeg_stream():
            """Stream MJPEG video data"""
            try:
                self.mjpeg_streamer.add_client()
                
                return StreamingResponse(
                    self.mjpeg_streamer.generate_mjpeg_stream(),
                    media_type="multipart/x-mixed-replace; boundary=frame",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0"
                    }
                )
                
            except Exception as e:
                self.logger.error(f"Error starting MJPEG stream: {e}")
                raise HTTPException(status_code=500, detail=str(e))
            finally:
                self.mjpeg_streamer.remove_client()
        
        @self.app.get("/")
        async def root():
            """Root endpoint with basic info"""
            return {
                "service": "focusd",
                "version": "1.0.0",
                "description": "Autofocus System for Raspberry Pi Zero W2",
                "endpoints": {
                    "status": "/status",
                    "config": "/config",
                    "focus": "/focus", 
                    "capture": "/capture",
                    "stream": "/stream",
                    "docs": "/docs"
                }
            }
    
    def update_focus_data(self, focus_data: Dict[str, Any]):
        """Update latest focus data"""
        self.latest_focus_data = focus_data
    
    def _format_uptime(self, uptime_seconds: float) -> str:
        """Format uptime in human-readable format"""
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    async def _reload_config(self):
        """Reload configuration (background task)"""
        try:
            self.config_manager.load_config()
            self.logger.info("Configuration reloaded")
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")
    
    def run(self, host: str = "0.0.0.0", port: int = 8080):
        """Run the FastAPI server"""
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )


def create_app(config_manager: ConfigManager, mjpeg_streamer: MJPEGStreamer) -> FastAPI:
    """Create FastAPI application"""
    api = FocusdAPI(config_manager, mjpeg_streamer)
    return api.app