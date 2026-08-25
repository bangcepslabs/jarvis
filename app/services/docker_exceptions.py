class DockerServiceError(Exception):
    """Base error for safe Docker service failures."""


class DockerUnavailableError(DockerServiceError):
    """Docker Engine cannot be reached."""


class ContainerNotFoundError(DockerServiceError):
    """The requested container does not exist."""
