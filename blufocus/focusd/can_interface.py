"""
CAN Bus Interface for focusd

Implements CAN bus communication for publishing focus metrics according to specification:
- socketcan driver
- Arbitration ID: 0x123 (configurable)
- Data payload: first 4 bytes little-endian IEEE-754 float = focus value
- Push mode: transmit every processed frame
- Pull mode: on receiving CAN message with ID 0x124, immediately send latest value
"""

import logging
import struct
import threading
import time
from typing import Optional, Callable
import can
from can import BusABC, Message


class CANInterface:
    """CAN bus interface for focus metric communication"""
    
    def __init__(self, interface: str = "can0", bitrate: int = 100000,
                 tx_id: int = 0x123, rx_id: int = 0x124):
        self.interface = interface
        self.bitrate = bitrate
        self.tx_id = tx_id
        self.rx_id = rx_id
        
        self.bus: Optional[BusABC] = None
        self.latest_focus_value: float = 0.0
        self.is_running = False
        self.push_mode_enabled = True
        self.pull_mode_enabled = True
        
        self.logger = logging.getLogger(__name__)
        self._listener_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
    def start(self) -> bool:
        """Initialize and start CAN interface"""
        try:
            # Initialize CAN bus
            self.bus = can.interface.Bus(channel=self.interface, 
                                       bustype='socketcan',
                                       bitrate=self.bitrate)
            
            self.is_running = True
            
            # Start listener thread for pull mode
            if self.pull_mode_enabled:
                self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self._listener_thread.start()
                
            self.logger.info(f"CAN interface started on {self.interface} at {self.bitrate} bps")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start CAN interface: {e}")
            return False
    
    def stop(self):
        """Stop CAN interface"""
        self.is_running = False
        
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
            
        if self.bus:
            self.bus.shutdown()
            self.bus = None
            
        self.logger.info("CAN interface stopped")
    
    def publish_focus_value(self, focus_value: float) -> bool:
        """
        Publish focus value to CAN bus (push mode)
        
        Args:
            focus_value: Focus metric value to publish
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.bus or not self.push_mode_enabled:
            return False
            
        try:
            with self._lock:
                self.latest_focus_value = focus_value
                
            # Pack focus value as little-endian IEEE-754 float (4 bytes)
            # Remaining 4 bytes are reserved (filled with zeros)
            data = struct.pack('<f', focus_value) + b'\x00\x00\x00\x00'
            
            message = Message(arbitration_id=self.tx_id, data=data, is_extended_id=False)
            self.bus.send(message)
            
            self.logger.debug(f"Published focus value: {focus_value:.6f}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish focus value: {e}")
            return False
    
    def _listen_loop(self):
        """Listen for CAN messages (pull mode)"""
        if not self.bus:
            return
            
        while self.is_running:
            try:
                # Listen for messages with timeout
                message = self.bus.recv(timeout=0.1)
                
                if message is None:
                    continue
                    
                # Check if this is a request for focus value
                if message.arbitration_id == self.rx_id:
                    self._handle_focus_request(message)
                    
            except Exception as e:
                if self.is_running:  # Only log if we're not shutting down
                    self.logger.error(f"Error in CAN listener: {e}")
                break
    
    def _handle_focus_request(self, message: Message):
        """Handle incoming focus value request"""
        try:
            with self._lock:
                focus_value = self.latest_focus_value
                
            # Send current focus value immediately
            self.publish_focus_value(focus_value)
            self.logger.debug(f"Responded to focus request with value: {focus_value:.6f}")
            
        except Exception as e:
            self.logger.error(f"Failed to handle focus request: {e}")
    
    def update_latest_focus(self, focus_value: float):
        """Update the latest focus value (used by pull mode)"""
        with self._lock:
            self.latest_focus_value = focus_value
    
    def get_latest_focus(self) -> float:
        """Get the latest focus value"""
        with self._lock:
            return self.latest_focus_value
    
    def set_push_mode(self, enabled: bool):
        """Enable/disable push mode"""
        self.push_mode_enabled = enabled
        self.logger.info(f"Push mode {'enabled' if enabled else 'disabled'}")
    
    def set_pull_mode(self, enabled: bool):
        """Enable/disable pull mode"""
        old_enabled = self.pull_mode_enabled
        self.pull_mode_enabled = enabled
        
        # Start listener thread if enabling pull mode
        if enabled and not old_enabled and self.is_running:
            if not self._listener_thread or not self._listener_thread.is_alive():
                self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self._listener_thread.start()
                
        self.logger.info(f"Pull mode {'enabled' if enabled else 'disabled'}")
    
    def is_connected(self) -> bool:
        """Check if CAN interface is connected and running"""
        return self.is_running and self.bus is not None


def setup_can_interface(interface: str = "can0", bitrate: int = 100000) -> bool:
    """
    Setup CAN interface using system commands
    
    This should be called before starting the CAN interface, typically
    in a systemd service or startup script.
    """
    import subprocess
    
    try:
        # Bring down interface first
        subprocess.run(['ip', 'link', 'set', interface, 'down'], 
                      check=False, capture_output=True)
        
        # Configure CAN interface
        subprocess.run(['ip', 'link', 'set', interface, 'type', 'can', 
                       'bitrate', str(bitrate)], check=True, capture_output=True)
        
        # Bring up interface
        subprocess.run(['ip', 'link', 'set', interface, 'up'], 
                      check=True, capture_output=True)
        
        logging.info(f"CAN interface {interface} configured at {bitrate} bps")
        return True
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to setup CAN interface: {e}")
        return False
    except Exception as e:
        logging.error(f"Error setting up CAN interface: {e}")
        return False