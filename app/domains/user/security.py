"""Password hashing utilities using passlib with bcrypt.

This module provides secure password hashing and verification
using the bcrypt algorithm via passlib.
"""

from passlib.context import CryptContext

# Configure passlib to use bcrypt as the default hashing scheme
# - bcrypt: Industry standard, secure, and slow (good for passwords)
# - deprecated="auto": Automatically upgrade hashes if scheme changes
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Cost factor (2^12 iterations)
)


class PasswordHasher:
    """Handles password hashing and verification using bcrypt.
    
    This class provides a clean interface for password operations
    using passlib's bcrypt implementation.
    
    Example:
        hasher = PasswordHasher()
        hashed = hasher.hash("my_secure_password")
        is_valid = hasher.verify("my_secure_password", hashed)
    """

    @staticmethod
    def hash(password: str) -> str:
        """Hash a plain text password.
        
        Args:
            password: The plain text password to hash
            
        Returns:
            The bcrypt hashed password string
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain text password against a hash.
        
        Args:
            plain_password: The plain text password to verify
            hashed_password: The bcrypt hash to verify against
            
        Returns:
            True if the password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        """Check if a password hash needs to be rehashed.
        
        This is useful when upgrading the hashing algorithm
        or changing the cost factor.
        
        Args:
            hashed_password: The existing hash to check
            
        Returns:
            True if the hash should be regenerated
        """
        return pwd_context.needs_update(hashed_password)


# Convenience functions for direct usage
def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The bcrypt hashed password string
    """
    return PasswordHasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a bcrypt hash.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hash to verify against
        
    Returns:
        True if the password matches, False otherwise
    """
    return PasswordHasher.verify(plain_password, hashed_password)
