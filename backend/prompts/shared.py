from typing import Dict, Any, List

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"
