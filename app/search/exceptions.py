class SearchError(Exception):
    """Safe, provider-independent search failure."""


class SearchUnavailableError(SearchError):
    pass


class SearchNoResultsError(SearchError):
    pass
