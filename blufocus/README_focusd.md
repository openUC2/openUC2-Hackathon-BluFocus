# focusd - Autofocus System for Raspberry Pi Zero W2

A lightweight autofocus system that acquires camera frames, evaluates focus quality, streams video for debugging, exposes runtime configuration via REST API, and publishes per-frame focus metrics over CAN bus.

## Features

- **Real-time focus computation** using double/single Gaussian fitting algorithm
- **Camera capture** at ≤15 fps using libcamera (with fallbacks)
- **MJPEG video streaming** over HTTPS for live debugging (avoids mixed content issues)
- **REST API** for configuration and control (served over HTTPS by default)
- **CAN bus interface** for real-time focus metrics (push/pull modes)
- **Configuration persistence** with YAML files
- **SystemD integration** for auto-start and monitoring
- **Performance optimized** for Raspberry Pi Zero W2
- **Automatic SSL certificate generation** for secure communication

## Requirements

### Hardware
- Raspberry Pi Zero W2 (1 GHz quad-core, 512 MB RAM)
- CSI-2 camera (e.g., HQ camera with manual exposure & gain)
- Waveshare RS485_CAN_HAT connected to Pi GPIO/SPI
- 2.4 GHz Wi-Fi connectivity

### Software
- Raspberry Pi OS Lite 64-bit (Debian 12)
- Python ≥3.11
- See `requirements.txt` for Python dependencies

## Quick Start

### 1. Flash and Boot

Flash the provided `focusd-YYYYMMDD.img` to an SD card:

```bash
#  use Raspberry Pi Imager with the .img file
```

### 2. Initial Setup

1. Insert SD card and boot Pi
2. Connect to predefined Wi-Fi network
3. Find Pi IP address (check router or use `nmap`)
4. Access live video stream: `https://<pi-ip>:8080/stream` (HTTPS enabled by default)
   - **Note**: You may need to accept the self-signed certificate warning in your browser

### 3. API Usage Examples

#### Swagger 

Visit https://<pi-ip>:8080/docs (served over HTTPS by default)

#### Check System Status
```bash
curl -k https://<pi-ip>:8080/status
```

#### Get Current Configuration
```bash
curl -k https://<pi-ip>:8080/config
```

#### Update Camera Settings
```bash
curl -k -X POST https://<pi-ip>:8080/config \
  -H "Content-Type: application/json" \
  -d '{"camera": {"exposure": 1500, "gain": 10}}'
```

#### Capture Single Frame
```bash
curl -k https://<pi-ip>:8080/capture > capture.jpg
```

#### Get Latest Focus Value
```bash
curl -k https://<pi-ip>:8080/focus
# Returns: {"t": 1686844861.012, "focus": 1.234}
```

**Note**: The `-k` flag tells curl to ignore SSL certificate errors (needed for self-signed certificates)

### 4. CAN Bus Monitoring

Monitor focus values on CAN bus:

```bash
# On Pi or connected device with can-utils
candump can0

# Example output:
# can0  123   [8]  3F 9D B2 2D 00 00 00 00  # Focus value as IEEE-754 float
```

Send focus request (pull mode):
```bash
cansend can0 124#
# Pi will immediately respond with latest focus value on ID 0x123
```

## 🏗️ Installation from Source

### On Raspberry Pi

```bash
# Clone repository
git clone https://github.com/openUC2/openUC2-Hackathon-BluFocus.git
cd openUC2-Hackathon-BluFocus/blufocus

# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip can-utils libopencv-dev

# Install Python dependencies
pip3 install -r requirements.txt

# Install focusd
sudo pip3 install -e .

# Setup CAN interface
sudo ./scripts/setup-can.sh

# Install systemd services
sudo cp scripts/focusd.service /etc/systemd/system/
sudo cp scripts/can0-setup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable focusd can0-setup

# Start services
sudo systemctl start can0-setup
sudo systemctl start focusd

# Check status
sudo systemctl status focusd
```

### For Development

```bash
# Clone and setup development environment
git clone https://github.com/openUC2/openUC2-Hackathon-BluFocus.git
cd openUC2-Hackathon-BluFocus

# Install with development dependencies
pip3 install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
flake8 .
black .

# Run in development mode
python3 -m focusd.main --config config.yaml --log-level DEBUG
```

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root endpoint with service info |
| `GET` | `/status` | System health, version, uptime |
| `GET` | `/config` | Current configuration (YAML) |
| `POST` | `/config` | Update configuration |
| `POST` | `/capture` | Capture single frame (JPEG) |
| `GET` | `/focus` | Latest focus value (JSON) |
| `GET` | `/stream` | MJPEG video stream |
| `GET` | `/docs` | Swagger documentation |

### Configuration Structure

```yaml
camera:
  fps: 10
  exposure: 1000  # microseconds
  gain: 0         # 0-30
  width: 320
  height: 240

focus_algorithm:
  gaussian_sigma: 11.0
  background_threshold: 40
  crop_radius: 300
  enable_gaussian_blur: true

can:
  interface: "can0"
  bitrate: 100000
  arbitration_id_tx: 0x123
  arbitration_id_rx: 0x124
  enable_push_mode: true
  enable_pull_mode: true

api:
  host: "0.0.0.0"
  port: 8080
  enable_docs: true
  cors_enabled: true
  enable_ssl: true  # HTTPS enabled by default
  ssl_cert_path: "/etc/focusd/ssl/cert.pem"
  ssl_key_path: "/etc/focusd/ssl/key.pem"

system:
  log_level: "INFO"
  config_file: "/etc/focusd/config.yaml"
  pid_file: "/var/run/focusd.pid"
```

### HTTPS Configuration

HTTPS is enabled by default to prevent mixed content issues when accessing the video stream from HTTPS web pages. The system automatically generates self-signed certificates if they don't exist.

#### Disabling HTTPS (not recommended)
```yaml
api:
  enable_ssl: false
```

#### Custom SSL Certificates
Replace the auto-generated certificates with your own:
```bash
sudo cp your-cert.pem /etc/focusd/ssl/cert.pem
sudo cp your-key.pem /etc/focusd/ssl/key.pem
sudo systemctl restart focusd
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_focus_algorithm.py -v
pytest tests/test_focusd.py::TestConfigManager -v

# Run with coverage
pytest tests/ --cov=focusd --cov=algorithms --cov=api
```

### Manual Testing

```bash
# Test focus algorithm with synthetic data
python3 tests/test_focus_algorithm.py

# Test camera interface (dummy mode)
python3 -c "
from focusd.camera import CameraInterface
camera = CameraInterface()
camera.start()
import time; time.sleep(2)
frame = camera.get_latest_frame()
print(f'Frame shape: {frame.shape if frame is not None else None}')
camera.stop()
"

# Test API endpoints
python3 -m focusd.main &
sleep 5
curl -k https://localhost:8080/status
curl -k https://localhost:8080/focus
pkill -f focusd.main
```

## Troubleshooting

### Common Issues

**Camera not working:**
```bash
# Check libcamera installation
libcamera-still --version

# Check camera detection
libcamera-hello --list-cameras

# Enable camera in config
sudo raspi-config  # Enable camera interface
```

**CAN interface issues:**
```bash
# Check CAN hardware
dmesg | grep -i can

# Manual CAN setup
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 100000
sudo ip link set can0 up

# Test CAN
cansend can0 123#DEADBEEF
candump can0
```

**Service not starting:**
```bash
# Check service status
sudo systemctl status focusd

# Check logs
sudo journalctl -u focusd -f

# Manual start for debugging
sudo -u focusd python3 -m focusd.main --log-level DEBUG
```

**Performance issues:**
```bash
# Monitor CPU usage
top -p $(pgrep -f focusd)

# Check memory usage
cat /proc/$(pgrep -f focusd)/status | grep VmRSS

# Monitor frame processing
sudo journalctl -u focusd -f | grep "Performance"
```

### Performance Targets

| Metric | Target | How to Check |
|--------|--------|--------------|
| CPU Usage | ≤70% of single core | `top`, check focusd process |
| RAM Usage | ≤120 MB resident | Check VmRSS in `/proc/PID/status` |
| Boot time | ≤25s to ready | `systemd-analyze critical-chain` |
| CAN latency | ≤40ms frame→publish | Check logs for timing warnings |

## 🔌 CAN Message Format

### Focus Value Publication (ID 0x123)
```
Bytes 0-3: Focus value (IEEE-754 float, little-endian)
Bytes 4-7: Reserved (0x00)
```

### Focus Request (ID 0x124)
```
Data: Empty (triggers immediate focus value response)
```

### Example CAN Traces

```bash
# Focus value 1.234 published
can0  123   [8]  3F 9D B2 2D 00 00 00 00

# Focus request
can0  124   [0]

# Immediate response with current value
can0  123   [8]  40 12 34 56 00 00 00 00
```

## 📊 Performance Monitoring

### Built-in Metrics

The service logs performance statistics every 30 seconds:

```bash
# View performance logs
sudo journalctl -u focusd -f | grep Performance

# Example output:
# Performance: 9.8 fps, 294 frames processed in 30.0s
```

### External Monitoring

```bash
# Monitor via API
curl http://<pi-ip>:8080/status

# Monitor CAN traffic
candump can0 -t a | grep 123

# System resources
htop
iotop
```

## 🔄 Building Custom Images

```bash
# Build Pi image with focusd
./scripts/build_image.sh

# This creates:
# - Pi-gen configuration for custom image
# - focusd distribution archive
# - Installation instructions
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push branch (`git push origin feature/amazing-feature`)
6. Open Pull Request

## 📞 Support

- **Issues**: https://github.com/openUC2/openUC2-Hackathon-BluFocus/issues
- **Discussions**: https://github.com/openUC2/openUC2-Hackathon-BluFocus/discussions
- **Wiki**: https://github.com/openUC2/openUC2-Hackathon-BluFocus/wiki

## 🏆 Acknowledgments

- openUC2 project for the hardware platform
- Original autofocus algorithm research
- Raspberry Pi Foundation for the platform
- Contributors and testers