"""Password hashing utilities using bcrypt.

This module provides secure password hashing and verification
using the bcrypt algorithm directly.
"""

import bcrypt


class PasswordHasher:
    """Handles password hashing and verification using bcrypt.
    
    This class provides a clean interface for password operations
    using bcrypt directly (avoiding passlib Python 3.14 issues).
    
    Example:
        hasher = PasswordHasher()
        hashed = hasher.hash("my_secure_password")
        is_valid = hasher.verify("my_secure_password", hashed)
    """

    @staticmethod
    def _truncate_password(password: str) -> bytes:
        """Truncate password to 72 bytes (bcrypt limit).
        
        Args:
            password: The plain text password
            
        Returns:
            Password encoded as bytes, truncated to 72 bytes
        """
        return password.encode('utf-8')[:72]

    @staticmethod
    def hash(password: str) -> str:
        """Hash a plain text password.
        
        Args:
            password: The plain text password to hash
            
        Returns:
            The bcrypt hashed password string
        """
        # Truncate to 72 bytes (bcrypt limit)
        truncated = PasswordHasher._truncate_password(password)
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(truncated, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain text password against a hash.
        
        Args:
            plain_password: The plain text password to verify
            hashed_password: The bcrypt hash to verify against
            
        Returns:
            True if the password matches, False otherwise
        """
        # Truncate to 72 bytes (bcrypt limit)
        truncated = PasswordHasher._truncate_password(plain_password)
        return bcrypt.checkpw(truncated, hashed_password.encode('utf-8'))

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        """Check if a password hash needs to be rehashed.
        
        Note: With direct bcrypt usage, we check the cost factor.
        Returns True if cost factor is less than 12.
        
        Args:
            hashed_password: The existing hash to check
            
        Returns:
            True if the hash should be regenerated
        """
        try:
            # bcrypt hash format: $2b$12$... where 12 is the cost factor
            parts = hashed_password.split('$')
            if len(parts) >= 3:
                cost = int(parts[2])
                return cost < 12
        except (ValueError, IndexError):
            pass
        return False


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
