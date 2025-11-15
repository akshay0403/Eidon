from __future__ import annotations

class EidonError(Exception):
    """
    Base user-facing error for Eidon CLI.

    Args:
        message: Short, user-friendly message.
        code: Process exit code to use when this error is raised.
    """
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = int(code)

EXIT_OK = 0
EXIT_USAGE = 2         # bad CLI usage, missing args, etc.
EXIT_RUNTIME = 3       # generic runtime error
EXIT_EXISTS = 4