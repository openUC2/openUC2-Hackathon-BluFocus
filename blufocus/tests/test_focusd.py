"""
Comprehensive unit tests for focusd autofocus system

Tests all components with synthetic frame fixtures as specified in section 10.5
"""

import pytest
import numpy as np
import tempfile
import os
import yaml
import time
from unittest.mock import Mock, patch
import sys

# Add project root to path
sys.path.append('/home/runner/work/openUC2-Hackathon-BluFocus/openUC2-Hackathon-BluFocus')

from algorithms.focus_algorithm import FocusMetric, FocusConfig
from focusd.config import ConfigManager, FocusdConfig
from focusd.camera import CameraInterface
from focusd.mjpeg_streamer import MJPEGStreamer
from focusd.can_interface import CANInterface


class TestFocusAlgorithm:
    """Test focus algorithm with synthetic frames"""
    
    @pytest.fixture
    def focus_metric(self):
        config = FocusConfig(gaussian_sigma=11, background_threshold=40)
        return FocusMetric(config)
    
    @pytest.fixture
    def sharp_frame(self):
        """Create a sharp synthetic frame"""
        frame = np.zeros((240, 320), dtype=np.uint8)
        # Sharp rectangular pattern
        frame[100:140, 140:180] = 255
        frame[110:130, 150:170] = 128
        return frame
    
    @pytest.fixture
    def blurry_frame(self):
        """Create a blurry synthetic frame"""
        from scipy.ndimage import gaussian_filter
        frame = np.zeros((240, 320), dtype=np.uint8)
        frame[100:140, 140:180] = 255
        frame[110:130, 150:170] = 128
        # Apply heavy blur
        return gaussian_filter(frame.astype(float), sigma=10).astype(np.uint8)
    
    def test_focus_computation_sharp_frame(self, focus_metric, sharp_frame):
        """Test focus computation on sharp frame"""
        result = focus_metric.compute(sharp_frame)
        
        assert 't' in result
        assert 'focus' in result
        assert isinstance(result['focus'], float)
        assert result['focus'] > 0  # Should have positive focus value
        assert not np.isnan(result['focus'])
        assert not np.isinf(result['focus'])
    
    def test_focus_computation_blurry_frame(self, focus_metric, blurry_frame):
        """Test focus computation on blurry frame"""
        result = focus_metric.compute(blurry_frame)
        
        assert 't' in result
        assert 'focus' in result
        assert isinstance(result['focus'], float)
        assert result['focus'] > 0
    
    def test_focus_comparison(self, focus_metric, sharp_frame, blurry_frame):
        """Test that sharp frame has different focus value than blurry frame"""
        sharp_result = focus_metric.compute(sharp_frame)
        blurry_result = focus_metric.compute(blurry_frame)
        
        # Focus values should be different (not necessarily higher/lower)
        assert sharp_result['focus'] != blurry_result['focus']
    
    def test_focus_config_update(self, focus_metric):
        """Test focus configuration updates"""
        original_sigma = focus_metric.config.gaussian_sigma
        
        focus_metric.update_config(gaussian_sigma=20.0)
        assert focus_metric.config.gaussian_sigma == 20.0
        
        with pytest.raises(ValueError):
            focus_metric.update_config(invalid_param=123)
    
    def test_grayscale_conversion(self, focus_metric):
        """Test RGB to grayscale conversion"""
        # Create RGB frame
        rgb_frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        
        result = focus_metric.compute(rgb_frame)
        assert 't' in result
        assert 'focus' in result
    
    def test_empty_frame(self, focus_metric):
        """Test handling of empty/black frame"""
        empty_frame = np.zeros((240, 320), dtype=np.uint8)
        
        result = focus_metric.compute(empty_frame)
        assert 't' in result
        assert 'focus' in result
        # Should handle gracefully (may return inf or nan)


class TestConfigManager:
    """Test configuration management"""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                'camera': {'fps': 15, 'exposure': 1000, 'gain': 5},
                'focus_algorithm': {'gaussian_sigma': 11.0, 'background_threshold': 40},
                'can': {'interface': 'can0', 'bitrate': 100000},
                'api': {'host': '0.0.0.0', 'port': 8080},
                'system': {'log_level': 'INFO'}
            }
            yaml.dump(config_data, f)
            yield f.name
        os.unlink(f.name)
    
    def test_load_config_from_file(self, temp_config_file):
        """Test loading configuration from file"""
        config_manager = ConfigManager(temp_config_file)
        config = config_manager.load_config()
        
        assert isinstance(config, FocusdConfig)
        assert config.camera.fps == 15
        assert config.focus_algorithm.gaussian_sigma == 11.0
    
    def test_create_default_config(self):
        """Test creating default configuration"""
        config_manager = ConfigManager('/nonexistent/path')
        config = config_manager.load_config()
        
        assert isinstance(config, FocusdConfig)
        assert config.camera.fps > 0
        assert config.api.port > 0
    
    def test_save_config(self, temp_config_file):
        """Test saving configuration"""
        config_manager = ConfigManager(temp_config_file)
        config = config_manager.load_config()
        
        # Modify config
        config.camera.fps = 20
        
        success = config_manager.save_config(config)
        assert success
        
        # Reload and verify
        new_config = config_manager.load_config()
        assert new_config.camera.fps == 20
    
    def test_update_config(self, temp_config_file):
        """Test partial configuration updates"""
        config_manager = ConfigManager(temp_config_file)
        config_manager.load_config()
        
        updates = {
            'camera': {'fps': 25},
            'api': {'port': 9090}
        }
        
        success = config_manager.update_config(updates)
        assert success
        
        updated_config = config_manager.get_config()
        assert updated_config.camera.fps == 25
        assert updated_config.api.port == 9090
    
    def test_config_validation(self, temp_config_file):
        """Test configuration validation"""
        config_manager = ConfigManager(temp_config_file)
        config = config_manager.load_config()
        
        # Valid config
        is_valid, errors = config_manager.validate_config(config)
        assert is_valid
        assert len(errors) == 0
        
        # Invalid config
        config.camera.fps = -1
        config.api.port = 99999
        
        is_valid, errors = config_manager.validate_config(config)
        assert not is_valid
        assert len(errors) > 0


class TestMJPEGStreamer:
    """Test MJPEG streaming functionality"""
    
    @pytest.fixture
    def mjpeg_streamer(self):
        return MJPEGStreamer(quality=85)
    
    @pytest.fixture
    def test_frame(self):
        return np.random.randint(0, 255, (240, 320), dtype=np.uint8)
    
    def test_update_frame(self, mjpeg_streamer, test_frame):
        """Test frame update"""
        mjpeg_streamer.start()
        mjpeg_streamer.update_frame(test_frame)
        
        assert mjpeg_streamer.has_frame()
        mjpeg_streamer.stop()
    
    def test_jpeg_encoding(self, mjpeg_streamer, test_frame):
        """Test JPEG encoding"""
        mjpeg_streamer.start()
        mjpeg_streamer.update_frame(test_frame)
        
        jpeg_data = mjpeg_streamer.get_frame_jpeg()
        assert jpeg_data is not None
        assert len(jpeg_data) > 0
        assert jpeg_data.startswith(b'\xff\xd8')  # JPEG header
        
        mjpeg_streamer.stop()
    
    def test_client_management(self, mjpeg_streamer):
        """Test client count management"""
        mjpeg_streamer.start()
        
        initial_count = mjpeg_streamer.get_client_count()
        mjpeg_streamer.add_client()
        assert mjpeg_streamer.get_client_count() == initial_count + 1
        
        mjpeg_streamer.remove_client()
        assert mjpeg_streamer.get_client_count() == initial_count
        
        mjpeg_streamer.stop()


class TestCameraInterface:
    """Test camera interface"""
    
    @pytest.fixture
    def camera(self):
        # Force dummy mode for testing
        with patch.object(CameraInterface, '_detect_camera_method', return_value='dummy'):
            return CameraInterface(width=320, height=240, fps=10)
    
    def test_camera_initialization(self, camera):
        """Test camera initialization"""
        assert camera.width == 320
        assert camera.height == 240
        assert camera.fps == 10
        assert not camera.is_running
    
    def test_camera_start_stop(self, camera):
        """Test camera start and stop"""
        success = camera.start()
        assert success
        assert camera.is_running
        
        # Wait a bit for frames
        time.sleep(0.5)
        
        frame = camera.get_latest_frame()
        assert frame is not None
        assert frame.shape == (240, 320)
        
        camera.stop()
        assert not camera.is_running
    
    def test_settings_update(self, camera):
        """Test camera settings update"""
        camera.update_settings(exposure=2000, gain=10)
        assert camera.exposure == 2000
        assert camera.gain == 10
        
        # Test bounds
        camera.update_settings(gain=50)  # Should be clamped to 30
        assert camera.gain == 30
    
    def test_single_frame_capture(self, camera):
        """Test single frame capture"""
        frame = camera.capture_single_frame()
        assert frame is not None
        assert frame.shape == (240, 320)
    
    def test_frame_callback(self, camera):
        """Test frame callback functionality"""
        callback_frames = []
        
        def frame_callback(frame):
            callback_frames.append(frame)
        
        camera.set_frame_callback(frame_callback)
        camera.start()
        
        # Wait for some frames
        time.sleep(1.0)
        
        camera.stop()
        
        assert len(callback_frames) > 0
        assert all(frame.shape == (240, 320) for frame in callback_frames)


class TestCANInterface:
    """Test CAN interface (mocked)"""
    
    @pytest.fixture
    def can_interface(self):
        # Mock CAN interface since we don't have real CAN hardware in CI
        with patch('can.interface.Bus') as mock_bus:
            interface = CANInterface()
            interface.bus = mock_bus
            interface.is_running = True
            return interface
    
    def test_focus_value_update(self, can_interface):
        """Test focus value updates"""
        can_interface.update_latest_focus(1.234)
        assert can_interface.get_latest_focus() == 1.234
    
    def test_push_pull_mode_control(self, can_interface):
        """Test push/pull mode enable/disable"""
        can_interface.set_push_mode(True)
        assert can_interface.push_mode_enabled
        
        can_interface.set_pull_mode(False)
        assert not can_interface.pull_mode_enabled
    
    @patch('can.interface.Bus')
    def test_can_message_publishing(self, mock_bus, can_interface):
        """Test CAN message publishing"""
        mock_bus_instance = Mock()
        mock_bus.return_value = mock_bus_instance
        can_interface.bus = mock_bus_instance
        
        success = can_interface.publish_focus_value(1.234)
        assert success
        mock_bus_instance.send.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])