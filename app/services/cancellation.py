"""Cooperative cancel flag for long-running library work.

Set when the user quits so ANLZ / analysis warm loops can stop instead of
holding the dedicated rekordbox thread until a full USB scan finishes.
"""

from __future__ import annotations

import threading

_quit_requested = threading.Event()


class OperationCancelled(Exception):
    """Raised when a blocking library operation stops because quit was requested."""


def request_quit() -> None:
    """
    Mark that the process should stop cooperative background work.

    Safe to call from the UI thread. Analysis loops poll ``quit_requested``.
    """
    _quit_requested.set()


def quit_requested() -> bool:
    """
    Return whether quit has been requested.

    Returns:
        True after ``request_quit`` until ``clear_quit_request``.
    """
    return _quit_requested.is_set()


def clear_quit_request() -> None:
    """
    Clear the quit flag.

    Used when a new app session starts and in tests so one quit does not
    poison later work in the same process.
    """
    _quit_requested.clear()


def raise_if_quit_requested() -> None:
    """
    Raise ``OperationCancelled`` when quit has been requested.

    Raises:
        OperationCancelled: When ``request_quit`` has been called.
    """
    if quit_requested():
        raise OperationCancelled("quit requested")
