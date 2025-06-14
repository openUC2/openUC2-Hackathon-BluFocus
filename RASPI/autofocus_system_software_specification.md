# Autofocus System Software Specification (Raspberry Pi Zero W2)

example code can be found in the folder /RASPI

## 1 Scope
Design and implement lightweight software that acquires camera frames, evaluates focus quality for each frame, streams video for debugging, exposes runtime configuration via REST, and publishes per‑frame focus metrics over CAN bus. Runs headless on Raspberry Pi Zero W2 and ships as a bootable OS image.

## 2 Target Hardware
| Component | Details |
|-----------|---------|
| SBC | Raspberry Pi Zero W2, 1 GHz quad‑core, 512 MB RAM |
| Camera | CSI‑2 camera (e.g. HQ camera); sensor supports manual exposure & gain |
| CAN | Waveshare RS485_CAN_HAT connected to Pi GPIO / SPI |
| Network | 2.4 GHz Wi‑Fi (credentials pre‑set via **boot.txt**) |

## 3 Operating System & Base Image
* Raspberry Pi OS Lite 64‑bit (Debian 12)
* Custom image built with `pi-gen`; Wi‑Fi SSID/PSK injected into `/boot/wpa_supplicant.conf`.
* Enable UART, I2C, SPI, and camera in `/boot/config.txt`.

## 4 Processes & Services
### 4.1 `focusd` – main service (Python ≥3.11)
* Captures frames from the CSI camera at ≤ 15 fps using `libcamera`.
* Applies user‑defined exposure & gain on each capture.
* Calls **FocusMetric.compute(frame)** (algorithm described in §5) and obtains a single `float` per frame.
* Publishes metric to CAN (event‑push every frame *and* on‑demand pull, §6).
* Exposes MJPEG stream of raw frames on `http://<pi>:8080/stream.mjpg` for live debug.
* Exposes REST API via FastAPI (see §7).
* Persists settings in `/etc/focusd/config.yaml`; loads on startup.
* Implemented as `systemd` service; auto‑restart.

### 4.2 `focusd_api` (FastAPI under Uvicorn)
Runs inside same process or separate; provides REST + WebSocket.

### 4.3 `can0` bring‑up script
```bash
ip link set can0 type can bitrate 100000
ifconfig can0 up
```
Add to `/etc/rc.local` or dedicated `systemd` service.

## 5 Focus Metric Algorithm
1. Convert frame to grayscale (`numpy uint8`).
2. (Optional) Gaussian blur σ ≈ 11 px to suppress noise.
3. Threshold: `im[im < background] = 0`, `background` configurable.
4. Compute mean projections `projX`, `projY`.
5. Fit `projX` with double‑Gaussian, `projY` with single‑Gaussian (SciPy `curve_fit`).
6. Focus value `F = σx / σy` (float32).
7. Return timestamped JSON `{ "t": 1686844861.012, "focus": F }`.

Provide `focus_algorithm.py` with clear API so algorithm can later be hot‑swapped or ported to C++.

## 6 CAN Bus Interface
* `socketcan` driver.
* Arbitration ID: `0x123` (configurable).
* Data payload: first 4 bytes little‑endian IEEE‑754 float = focus value; remaining bytes reserved.
* Push mode: transmit every processed frame.
* Pull mode: on receiving CAN message with ID `0x124`, immediately send latest value.
* Use `python‑can`; abstraction layer so C++ can reuse message format.

## 7 REST API (FastAPI)

This is mostly for debugging; useses Swagger

| Method & path | Purpose |
|---------------|---------|
| `GET /status` | health, version, uptime |
| `GET /config` | return current config YAML |
| `POST /config` | update config; body = partial YAML |
| `POST /capture` | grab single frame, return JPEG |
| `GET /focus` | latest focus value JSON |
| `GET /stream` | stream mjpeg data |


All writes trigger persistent save to `/etc/focusd/config.yaml`.

## 8 Performance Targets
* CPU ≤ 70 % of single core at 10 fps.
* RAM ≤ 120 MB resident.
* Boot‑to‑ready ≤ 25 s.
* CAN latency (frame → publish) ≤ 40 ms.

## 9 Logging & Monitoring
* `systemd‑journald` for service stdout/err.
* Optional MQTT publishing of metrics for remote dashboards.
* Rotate MJPEG stream to RAM‑disk to avoid SD wear.

## 10 Deployment & Deliverables
1. **Git repo** with structured modules:
   * `focusd/` core service
   * `api/` FastAPI app
   * `algorithms/` focus metrics
   * `scripts/` bring‑up, build‑image
2. **Dockerfile** for CI lint/unit‑tests (runs on x86 CI server).
3. **Pi image build script** (`build_image.sh`) producing `focusd-<date>.img`.
4. **README.md**: flashing instructions, API examples, CAN trace examples.
5. **Unit tests** (pytest) incl. synthetic frame fixtures.
6. **Benchmark report** against performance targets.
7. Optional: C++ port stub using `pybind11`.

## 11 Timeline (example)
| Week | Milestone |
|------|-----------|
| 1 | repo skeleton, CAN setup validated |
| 2 | camera capture + MJPEG + REST skeleton |
| 3 | algorithm integrated, unit tests passing |
| 4 | CAN push/pull implemented, performance tuned |
| 5 | image build pipeline, documentation, hand‑off |

## 12 Acceptance Criteria
* Flash image, power‑up Pi, connect to predefined Wi‑Fi, open `http://<pi>:8080/stream.mjpg` and see live video.
* `curl -X POST /config -d '{"exposure":1500}'` updates sensor and value persists after reboot.
* External CAN bus receives focus value for every frame within 40 ms.
* System meets performance & resource constraints.

---
End of specification.

