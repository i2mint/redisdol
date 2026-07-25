"""Pytest configuration for redisdol.

Lets the suite stay green **without a live Redis server**. ``redisdol`` is a
Redis data-object layer, so its module doctests (and any future tests) need a
reachable server. When none is reachable (e.g. a laptop with no ``redis-server``
running) the Redis-dependent items are *deselected* rather than left to fail;
when a server is available (local dev, or CI wired to a Redis service container)
they run normally.

The availability probe is a short TCP connect to the configured host/port
(default ``localhost:6379``). Override with ``REDISDOL_REDIS_HOST`` /
``REDISDOL_REDIS_PORT`` to point the probe elsewhere (e.g. to validate the
deselect behaviour, or at an external server) without touching the tests' own
connection defaults.
"""

import os
import pathlib
import socket

#: Default host/port the probe (and redisdol's own ``redis.Redis()`` defaults)
#: connect to.
_DFLT_REDIS_HOST = "localhost"
_DFLT_REDIS_PORT = 6379

#: Package-module stems whose doctests do NOT touch Redis and are therefore safe
#: to run without a server. Kept deliberately conservative: any module not listed
#: here has its doctests deselected when no Redis is reachable, so a new
#: Redis-using doctest can never silently pass-as-skipped in a way that hides a
#: real failure once a server is present. Widen only after verifying a module's
#: doctests are genuinely server-free.
_REDIS_FREE_DOCTEST_STEMS = frozenset({"util"})


def _redis_available(*, timeout_s=0.5):
    """Return ``True`` iff a Redis server accepts a TCP connection quickly."""
    host = os.environ.get("REDISDOL_REDIS_HOST", _DFLT_REDIS_HOST)
    try:
        port = int(os.environ.get("REDISDOL_REDIS_PORT", _DFLT_REDIS_PORT))
    except ValueError:
        port = _DFLT_REDIS_PORT
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _requires_redis(item):
    """Whether a collected item needs a live Redis to run.

    Any item under a ``tests`` directory is assumed to exercise a real store, and
    every package-module doctest except those in
    :data:`_REDIS_FREE_DOCTEST_STEMS` demonstrates a live store.
    """
    path = pathlib.Path(str(getattr(item, "path", None) or item.fspath))
    if "tests" in path.parts:
        return True
    return path.stem not in _REDIS_FREE_DOCTEST_STEMS


def pytest_collection_modifyitems(config, items):
    """Drop Redis-dependent items when no server is reachable.

    Uses *deselection* rather than a skip marker: some Redis-store classes are
    built dynamically (via dol store decorators), so their doctest items have no
    resolvable source line, and pytest >= 9 raises an ``INTERNALERROR`` while
    building a *skip report* for such an item. Deselected items never reach
    report generation, so this keeps the suite green without a server and is
    robust across pytest versions.
    """
    if _redis_available():
        return
    kept, deselected = [], []
    for item in items:
        (deselected if _requires_redis(item) else kept).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
