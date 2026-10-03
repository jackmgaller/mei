"""The one error shape every kit reports: a JSON Pointer path into the input and a message."""


class KitError(ValueError):
    def __init__(self, path, message):
        self.path = path
        super().__init__(message)


def pointer(path, key):
    """path extended by one JSON Pointer token (RFC 6901 escaping)."""
    return path+'/'+str(key).replace('~','~0').replace('/','~1')
