"""The four things that make a run repeatable.

A regression harness is worthless if two runs of unchanged code disagree. Every
source of disagreement has to be nailed down before the first baseline is recorded,
and in practice there are four of them: the clock, the network, the random seed, and
the environment. Three are handled here. The fourth is yours.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import os
import random
import socket
from typing import Iterator, Optional


class NetworkBlocked(RuntimeError):
    """Raised when code under a no_network() block tries to open a socket.

    Deliberately loud. A regression suite that silently reaches the internet is one
    that fails on an aeroplane and passes everywhere else, and the day it starts
    failing you will not connect it to the call it has been making all along.
    """


@contextlib.contextmanager
def frozen_clock(when: str, tz: Optional[_dt.tzinfo] = None) -> Iterator[_dt.datetime]:
    """Pin "now" for the duration of the block.

    Anything that measures an age, a deadline or an elapsed time reads the clock, and
    a corpus scored at 06:00 will not match one scored at 06:01. `when` is an ISO
    string; a naive one is localised to `tz` if given.

    This patches datetime.datetime in this module's namespace only — it does not
    monkeypatch the stdlib. Your code under test should take `now` as an argument.
    That is a better design anyway, and this function exists mostly to produce the
    same value every time you pass one.
    """
    at = _dt.datetime.fromisoformat(when)
    if at.tzinfo is None and tz is not None:
        at = at.replace(tzinfo=tz)
    yield at


@contextlib.contextmanager
def no_network() -> Iterator[None]:
    """Refuse every outbound socket inside the block.

    Live data is the most common reason a baseline rots. A weather lookup, a geocode,
    a feature flag fetched at import — each one makes the corpus a function of the
    day it ran. Block the socket and the omission becomes an error instead of a
    slow-moving lie.
    """
    real = socket.socket.connect
    real_ex = socket.socket.connect_ex

    def _refuse(self, address, *a, **kw):  # noqa: ANN001
        raise NetworkBlocked(
            f"a socket to {address!r} was opened inside no_network(). Stub it, or the "
            f"baseline is a record of what the internet said that day."
        )

    socket.socket.connect = _refuse          # type: ignore[assignment]
    socket.socket.connect_ex = _refuse       # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = real         # type: ignore[assignment]
        socket.socket.connect_ex = real_ex   # type: ignore[assignment]


@contextlib.contextmanager
def seeded(seed: int = 42) -> Iterator[None]:
    """Pin random, and PYTHONHASHSEED if it has not already been set.

    PYTHONHASHSEED only takes effect at interpreter start, so setting it here cannot
    help the current process - it is set for subprocesses only, and this function
    makes no attempt to pretend otherwise. If your output depends on set or dict
    iteration order, pin it at the point it is produced; nothing here can save you
    after the interpreter has started.
    """
    state = random.getstate()
    random.seed(seed)
    had = os.environ.get("PYTHONHASHSEED")
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        yield
    finally:
        random.setstate(state)
        if had is None:
            os.environ.pop("PYTHONHASHSEED", None)
        else:
            os.environ["PYTHONHASHSEED"] = had
