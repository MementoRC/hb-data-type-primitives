"""
Exceptions used across Hummingbot sub-packages.

Mirrors ``hummingbot/exceptions.py`` in the parent repo — the parent will
replace its copy with a re-export shim pointing here once this lands.
"""

from typing import Any


class HummingbotBaseException(Exception):  # noqa: N818
    """
    Most errors raised in Hummingbot should inherit this class so we can
    differentiate them from errors that come from dependencies.
    """


class ArgumentParserError(HummingbotBaseException):
    """
    Unable to parse a command (like start, stop, etc) from the hummingbot client
    """


class OracleRateUnavailable(HummingbotBaseException):
    """
    Asset value from third party is unavailable
    """


class InvalidScriptModule(HummingbotBaseException):
    """
    The file does not contain a ScriptBase subclass
    """


class InvalidController(HummingbotBaseException):
    """
    The file does not contain a ControllerBase subclass
    """


class OrderOutcomeUnknownError(HummingbotBaseException):
    """
    Raised when an order request's outcome is unknown (timeout or lost response).

    Callers must reconcile by ``client_order_id``. Downstream packages
    (market-connector) subclass it.
    """

    def __init__(self, message: str, *, client_order_id: str) -> None:
        super().__init__(message)
        self.client_order_id = client_order_id

    def __reduce__(self) -> tuple[Any, ...]:
        return (_rebuild_order_outcome_unknown, (type(self), str(self), self.client_order_id))


def _rebuild_order_outcome_unknown(
    cls: type[OrderOutcomeUnknownError], message: str, client_order_id: str
) -> OrderOutcomeUnknownError:
    return cls(message, client_order_id=client_order_id)
