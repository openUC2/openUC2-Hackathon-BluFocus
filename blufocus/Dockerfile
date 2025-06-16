# Dockerfile for focusd CI testing on x86 servers
# As specified in section 10.2

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    can-utils \
    libopencv-dev \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Create directories for config and logs
RUN mkdir -p /etc/focusd /var/log/focusd

# Create default config for testing
RUN python3 -c "\
from focusd.config import ConfigManager; \
cm = ConfigManager('/etc/focusd/config.yaml'); \
cm.load_config(); \
cm.save_config()"

# Expose API port
EXPOSE 8080

# Run tests by default
CMD ["python", "-m", "pytest", "tests/", "-v"]

# Alternative commands for different purposes:
# Run linter: docker run focusd flake8 .
# Run service: docker run -p 8080:8080 focusd python -m focusd.main
# Run shell: docker run -it focusd bash