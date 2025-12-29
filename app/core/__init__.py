"""Core module - Settings, Security, and shared utilities.

Note: Dependencies (deps.py) and auth modules are imported lazily
to avoid circular imports. Import them directly where needed:

    from app.core.deps import get_current_user, ActiveUser
    from app.core.auth import create_token_pair
    from app.core.exceptions import InvalidTokenError
"""

from app.core.config import settings

__all__ = [
    "settings",
]
