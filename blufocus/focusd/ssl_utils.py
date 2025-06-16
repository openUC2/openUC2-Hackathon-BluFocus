"""
SSL/TLS certificate utilities for focusd

Provides functionality to generate self-signed certificates for HTTPS support.
"""

import os
import logging
import ipaddress
import socket
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta


def get_local_ip_addresses():
    """Get local IP addresses for certificate generation"""
    ips = []
    try:
        # Get local IP by connecting to a remote address
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            ips.append(local_ip)
    except Exception:
        pass
    
    # Add common default addresses
    common_ips = ["127.0.0.1", "0.0.0.0"]
    for ip in common_ips:
        if ip not in ips:
            ips.append(ip)
    
    return ips


def generate_self_signed_cert(cert_path: str, key_path: str, 
                            common_name: str = "focusd",
                            validity_days: int = 365) -> bool:
    """
    Generate a self-signed certificate and private key.
    
    Args:
        cert_path: Path to save the certificate file
        key_path: Path to save the private key file
        common_name: Common name for the certificate
        validity_days: Certificate validity period in days
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Ensure directories exist
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenUC2"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Build Subject Alternative Name list
        san_list = [
            x509.DNSName("localhost"),
            x509.DNSName("*.local"),
            x509.DNSName("raspberrypi"),
            x509.DNSName("raspberrypi.local"),
            x509.DNSName("focusd"),
            x509.DNSName("focusd.local"),
        ]
        
        # Add IP addresses
        local_ips = get_local_ip_addresses()
        for ip_str in local_ips:
            try:
                san_list.append(x509.IPAddress(ipaddress.IPv4Address(ip_str)))
            except Exception as e:
                logger.warning(f"Failed to add IP {ip_str} to certificate: {e}")
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write private key to file
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Set restrictive permissions on private key
        os.chmod(key_path, 0o600)
        
        # Write certificate to file
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
        logger.info(f"Generated self-signed certificate: {cert_path}")
        logger.info(f"Generated private key: {key_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate self-signed certificate: {e}")
        return False


def ensure_certificates_exist(cert_path: str, key_path: str) -> bool:
    """
    Ensure SSL certificates exist, generating them if necessary.
    
    Args:
        cert_path: Path to certificate file
        key_path: Path to private key file
        
    Returns:
        True if certificates exist or were created successfully
    """
    logger = logging.getLogger(__name__)
    
    # Check if both files exist
    if os.path.exists(cert_path) and os.path.exists(key_path):
        logger.info(f"SSL certificates found: {cert_path}, {key_path}")
        return True
    
    # Generate new certificates
    logger.info("SSL certificates not found, generating self-signed certificates...")
    return generate_self_signed_cert(cert_path, key_path)


def validate_certificates(cert_path: str, key_path: str) -> bool:
    """
    Validate that certificate and key files are valid and match.
    
    Args:
        cert_path: Path to certificate file
        key_path: Path to private key file
        
    Returns:
        True if certificates are valid
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Check if files exist
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            return False
        
        # Load and validate certificate
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        
        # Load and validate private key
        with open(key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        
        # Check if certificate is expired
        now = datetime.utcnow()
        if now < cert.not_valid_before or now > cert.not_valid_after:
            logger.warning("SSL certificate is expired or not yet valid")
            return False
        
        # Verify that the private key matches the certificate
        cert_public_key = cert.public_key()
        private_public_key = private_key.public_key()
        
        # Compare public key components
        cert_numbers = cert_public_key.public_numbers()
        private_numbers = private_public_key.public_numbers()
        
        if cert_numbers.n != private_numbers.n or cert_numbers.e != private_numbers.e:
            logger.error("SSL certificate and private key do not match")
            return False
        
        logger.info("SSL certificates validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"SSL certificate validation failed: {e}")
        return False