"""
Configuration management for focusd autofocus system

Handles loading, saving, and updating configuration from YAML files.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, fields
from pathlib import Path


@dataclass
class CameraConfig:
    """Camera configuration parameters"""
    fps: int = 10
    exposure: int = 1000  # microseconds
    gain: int = 0  # 0-30
    width: int = 320
    height: int = 240


@dataclass 
class FocusAlgorithmConfig:
    """Focus algorithm configuration"""
    gaussian_sigma: float = 11.0
    background_threshold: int = 40
    crop_radius: int = 300
    enable_gaussian_blur: bool = True


@dataclass
class CANConfig:
    """CAN bus configuration"""
    interface: str = "can0"
    bitrate: int = 100000
    arbitration_id_tx: int = 0x123  # For sending focus values
    arbitration_id_rx: int = 0x124  # For receiving requests
    enable_push_mode: bool = True
    enable_pull_mode: bool = True


@dataclass
class APIConfig:
    """FastAPI configuration"""
    host: str = "0.0.0.0"
    port: int = 8080
    enable_docs: bool = True
    cors_enabled: bool = True
    enable_ssl: bool = False
    ssl_cert_path: str = "/etc/focusd/ssl/cert.pem"
    ssl_key_path: str = "/etc/focusd/ssl/key.pem"


@dataclass
class SystemConfig:
    """System-wide configuration"""
    log_level: str = "INFO"
    config_file: str = "/etc/focusd/config.yaml"
    pid_file: str = "/var/run/focusd.pid"
    max_frame_buffer_size: int = 10


@dataclass
class FocusdConfig:
    """Complete focusd configuration"""
    camera: CameraConfig
    focus_algorithm: FocusAlgorithmConfig
    can: CANConfig
    api: APIConfig
    system: SystemConfig
    
    def __post_init__(self):
        """Initialize sub-configs from dicts if needed"""
        if isinstance(self.camera, dict):
            self.camera = CameraConfig(**self.camera)
        if isinstance(self.focus_algorithm, dict):
            self.focus_algorithm = FocusAlgorithmConfig(**self.focus_algorithm)
        if isinstance(self.can, dict):
            self.can = CANConfig(**self.can)
        if isinstance(self.api, dict):
            self.api = APIConfig(**self.api)
        if isinstance(self.system, dict):
            self.system = SystemConfig(**self.system)


class ConfigManager:
    """Configuration manager for focusd"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/etc/focusd/config.yaml"
        self.config: Optional[FocusdConfig] = None
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> FocusdConfig:
        """Load configuration from file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config_dict = yaml.safe_load(f)
                self.config = FocusdConfig(**config_dict)
                self.logger.info(f"Configuration loaded from {self.config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load config from {self.config_path}: {e}")
                self.config = self._create_default_config()
        else:
            self.logger.info(f"Config file {self.config_path} not found, using defaults")
            self.config = self._create_default_config()
            
        return self.config
    
    def save_config(self, config: Optional[FocusdConfig] = None) -> bool:
        """Save configuration to file"""
        config = config or self.config
        if not config:
            raise ValueError("No configuration to save")
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Convert to dict for YAML serialization
            config_dict = asdict(config)
            
            with open(self.config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                
            self.logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save config to {self.config_path}: {e}")
            return False
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with partial updates"""
        if not self.config:
            self.load_config()
            
        try:
            # Apply updates to the configuration
            for section, values in updates.items():
                if hasattr(self.config, section):
                    section_config = getattr(self.config, section)
                    if isinstance(values, dict):
                        for key, value in values.items():
                            if hasattr(section_config, key):
                                setattr(section_config, key, value)
                            else:
                                self.logger.warning(f"Unknown config key: {section}.{key}")
                    else:
                        self.logger.warning(f"Invalid update format for section: {section}")
                else:
                    self.logger.warning(f"Unknown config section: {section}")
                    
            # Save updated configuration
            return self.save_config()
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            return False
    
    def get_config(self) -> FocusdConfig:
        """Get current configuration"""
        if not self.config:
            self.load_config()
        return self.config
    
    def _create_default_config(self) -> FocusdConfig:
        """Create default configuration"""
        return FocusdConfig(
            camera=CameraConfig(),
            focus_algorithm=FocusAlgorithmConfig(),
            can=CANConfig(),
            api=APIConfig(),
            system=SystemConfig()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        if not self.config:
            self.load_config()
        return asdict(self.config)
    
    def validate_config(self, config: Optional[FocusdConfig] = None) -> tuple[bool, list[str]]:
        """Validate configuration and return any errors"""
        config = config or self.config
        if not config:
            return False, ["No configuration available"]
            
        errors = []
        
        # Validate camera config
        if config.camera.fps <= 0 or config.camera.fps > 60:
            errors.append("Camera FPS must be between 1 and 60")
        if config.camera.exposure < 0:
            errors.append("Camera exposure must be non-negative")
        if config.camera.gain < 0 or config.camera.gain > 30:
            errors.append("Camera gain must be between 0 and 30")
            
        # Validate CAN config
        if config.can.bitrate <= 0:
            errors.append("CAN bitrate must be positive")
        if config.can.arbitration_id_tx < 0 or config.can.arbitration_id_tx > 0x7FF:
            errors.append("CAN TX arbitration ID must be valid (0-0x7FF)")
        if config.can.arbitration_id_rx < 0 or config.can.arbitration_id_rx > 0x7FF:
            errors.append("CAN RX arbitration ID must be valid (0-0x7FF)")
            
        # Validate API config
        if config.api.port <= 0 or config.api.port > 65535:
            errors.append("API port must be between 1 and 65535")
        
        # Validate SSL config if enabled
        if config.api.enable_ssl:
            if not config.api.ssl_cert_path or not config.api.ssl_key_path:
                errors.append("SSL certificate and key paths must be specified when SSL is enabled")
            
        return len(errors) == 0, errors