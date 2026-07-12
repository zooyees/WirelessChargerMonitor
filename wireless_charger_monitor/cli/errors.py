"""CLI error codes and exceptions."""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_DEVICE = 3

DEVICE_CODES = frozenset({
    'PORT_NOT_FOUND',
    'PORT_BUSY',
    'SCOPE_NOT_FOUND',
    'SCOPE_CAPTURE_FAILED',
    'SERIAL_TIMEOUT',
})


class CliError(Exception):
    """Raised for expected CLI failures that map to JSON error envelopes."""

    def __init__(self, code: str, message: str, hint: str | None = None, exit_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        if exit_code is not None:
            self.exit_code = exit_code
        elif code == 'INVALID_ARGS':
            self.exit_code = EXIT_USAGE
        elif code in DEVICE_CODES:
            self.exit_code = EXIT_DEVICE
        else:
            self.exit_code = EXIT_ERROR

    def to_dict(self) -> dict:
        err = {'code': self.code, 'message': self.message}
        if self.hint:
            err['hint'] = self.hint
        return err
