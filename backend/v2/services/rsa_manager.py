"""
RFID Marathon Management System - RSA Encryption Manager
Security Level: Military-grade
Last Updated: January 21, 2026

This module manages RSA public/private key encryption for API responses.
Participant names are encrypted using RSA public key before sending to frontend.
Frontend decrypts using private key.
"""

import logging
import base64
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

from constants import RSA_KEY_SIZE, EnvVars
from basefunctions import (
    get_env_variable,
    ensure_directory_exists,
    EncryptionError,
)

logger = logging.getLogger(__name__)


class RSAManager:
    """
    Manages RSA public/private key encryption for API responses.
    """
    
    def __init__(self):
        """Initialize RSA manager by loading or generating keys"""
        self.public_key: Optional[rsa.RSAPublicKey] = None
        self.private_key: Optional[rsa.RSAPrivateKey] = None
        self._load_or_generate_keys()
    
    def _load_or_generate_keys(self) -> None:
        """
        Load RSA keys from files or generate new ones if they don't exist.
        """
        public_key_path = get_env_variable(
            EnvVars.RSA_PUBLIC_KEY_PATH,
            required=False,
            default="keys/rsa_public.pem"
        ) or "keys/rsa_public.pem"
        private_key_path = get_env_variable(
            EnvVars.RSA_PRIVATE_KEY_PATH,
            required=False,
            default="keys/rsa_private.pem"
        ) or "keys/rsa_private.pem"
        
        public_key_file = Path(public_key_path)
        private_key_file = Path(private_key_path)
        
        # Check if keys exist
        if public_key_file.exists() and private_key_file.exists():
            try:
                self._load_keys_from_file(public_key_file, private_key_file)
                logger.info("✓ RSA keys loaded from files")
                return
            except Exception as e:
                logger.warning(f"Failed to load existing keys: {e}")
                logger.info("Generating new keys...")
        
        # Generate new keys if they don't exist or failed to load
        self._generate_and_save_keys(public_key_file, private_key_file)
        logger.info("✓ New RSA keys generated and saved")
    
    def _load_keys_from_file(
        self, 
        public_key_file: Path, 
        private_key_file: Path
    ) -> None:
        """
        Load RSA keys from PEM files.
        
        Args:
            public_key_file: Path to public key file
            private_key_file: Path to private key file
            
        Raises:
            EncryptionError: If keys cannot be loaded
        """
        try:
            # Load public key
            with open(public_key_file, 'rb') as f:
                public_key_pem = f.read()
                loaded_public_key = serialization.load_pem_public_key(
                    public_key_pem,
                    backend=default_backend()
                )
                if not isinstance(loaded_public_key, rsa.RSAPublicKey):
                    raise EncryptionError("Loaded public key is not an RSA public key")
                self.public_key = loaded_public_key
            
            # Load private key
            with open(private_key_file, 'rb') as f:
                private_key_pem = f.read()
                loaded_private_key = serialization.load_pem_private_key(
                    private_key_pem,
                    password=None,  # No password protection for backend keys
                    backend=default_backend()
                )
                if not isinstance(loaded_private_key, rsa.RSAPrivateKey):
                    raise EncryptionError("Loaded private key is not an RSA private key")
                self.private_key = loaded_private_key
            
            logger.info(f"Loaded RSA keys from {public_key_file} and {private_key_file}")
            
        except Exception as e:
            logger.error(f"Failed to load RSA keys: {e}")
            raise EncryptionError(f"Failed to load RSA keys: {str(e)}")
    
    def _generate_and_save_keys(
        self, 
        public_key_file: Path, 
        private_key_file: Path
    ) -> None:
        """
        Generate new RSA key pair and save to files.
        
        Args:
            public_key_file: Path to save public key
            private_key_file: Path to save private key
            
        Raises:
            EncryptionError: If key generation fails
        """
        try:
            # Generate private key
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=RSA_KEY_SIZE,
                backend=default_backend()
            )
            
            # Generate public key from private key
            self.public_key = self.private_key.public_key()
            
            # Ensure directory exists
            ensure_directory_exists(str(public_key_file.parent))
            
            # Save public key
            public_key_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            with open(public_key_file, 'wb') as f:
                f.write(public_key_pem)
            
            # Save private key
            private_key_pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()  # No password
            )
            with open(private_key_file, 'wb') as f:
                f.write(private_key_pem)
            
            logger.info(f"Generated and saved RSA keys to {public_key_file} and {private_key_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate RSA keys: {e}")
            raise EncryptionError(f"Failed to generate RSA keys: {str(e)}")
    
    def encrypt_with_public_key(self, plaintext: str) -> str:
        """
        Encrypt plaintext using public key.
        Used by backend to encrypt data before sending to frontend.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            str: Base64-encoded encrypted data
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")
        
        public_key = self.public_key
        if public_key is None:
            raise EncryptionError("Public key not initialized")
        
        try:
            plaintext_bytes = plaintext.encode('utf-8')
            
            # Encrypt with RSA-OAEP padding
            encrypted_bytes = public_key.encrypt(
                plaintext_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Encode to base64 for transport
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            
            logger.debug(f"RSA encrypted data (length: {len(plaintext)} -> {len(encrypted_b64)})")
            return encrypted_b64
            
        except Exception as e:
            logger.error(f"RSA encryption failed: {e}")
            raise EncryptionError(f"RSA encryption failed: {str(e)}")
    
    def decrypt_with_private_key(self, encrypted_b64: str) -> str:
        """
        Decrypt RSA-encrypted data using private key.
        Used by backend for testing. Frontend will use this method too.
        
        Args:
            encrypted_b64: Base64-encoded encrypted data
            
        Returns:
            str: Decrypted plaintext
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not encrypted_b64:
            raise EncryptionError("Cannot decrypt empty string")
        
        private_key = self.private_key
        if private_key is None:
            raise EncryptionError("Private key not initialized")
        
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_b64.encode('utf-8'))
            
            # Decrypt with RSA-OAEP padding
            decrypted_bytes = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            plaintext = decrypted_bytes.decode('utf-8')
            
            logger.debug(f"RSA decrypted data (length: {len(encrypted_b64)} -> {len(plaintext)})")
            return plaintext
            
        except Exception as e:
            logger.error(f"RSA decryption failed: {e}")
            raise EncryptionError(f"RSA decryption failed: {str(e)}")
    
    def export_public_key_pem(self) -> str:
        """
        Export public key in PEM format for frontend.
        
        Returns:
            str: PEM-encoded public key
        """
        if not self.public_key:
            raise EncryptionError("Public key not initialized")
        
        public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return public_key_pem.decode('utf-8')
    
    def export_private_key_pem(self) -> str:
        """
        Export private key in PEM format for frontend.
        
        Returns:
            str: PEM-encoded private key
        """
        if not self.private_key:
            raise EncryptionError("Private key not initialized")
        
        private_key_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return private_key_pem.decode('utf-8')


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_rsa_manager = None


def get_rsa_manager() -> RSAManager:
    """
    Get global RSA manager instance.
    
    Returns:
        RSAManager: Singleton instance
    """
    global _rsa_manager
    
    if _rsa_manager is None:
        _rsa_manager = RSAManager()
    
    return _rsa_manager
