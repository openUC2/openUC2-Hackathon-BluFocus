#!/bin/bash
# Setup CAN interface for focusd
# Based on specification section 4.3

set -e

INTERFACE=${1:-can0}
BITRATE=${2:-100000}

echo "Setting up CAN interface $INTERFACE at $BITRATE bps..."

# Bring down interface first (ignore errors)
ip link set $INTERFACE down 2>/dev/null || true

# Configure CAN interface
ip link set $INTERFACE type can bitrate $BITRATE

# Bring up interface  
ip link set $INTERFACE up

echo "CAN interface $INTERFACE is up and configured"

# Show interface status
ip link show $INTERFACE