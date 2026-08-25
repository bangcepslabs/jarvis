class JarvisError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(JarvisError):
    """Raised when a configured component cannot be created."""
