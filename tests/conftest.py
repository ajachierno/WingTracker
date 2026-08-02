"""Shared test fixtures."""
import sys
from pathlib import Path

import pytest

# Make the repo root importable as `custom_components.wing_delivery...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in tests."""
    yield


# --- Windows-only test environment compatibility ---------------------------
# Home Assistant core (and therefore pytest-homeassistant-custom-component)
# is not officially tested on native Windows -- see
# https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/154
# where the maintainer confirms this exact failure is out of scope upstream.
#
# The concrete problem: on Windows, asyncio's ProactorEventLoop opens an
# internal loopback "self-pipe" using an AF_INET socket.socketpair()
# (Windows has no native AF_UNIX socketpair, so CPython falls back to a
# loopback TCP pair). But the plugin's per-test setup
# (pytest_homeassistant_custom_component.plugins.pytest_runtest_setup) calls
# pytest_socket.disable_socket(allow_unix_socket=True), whose GuardedSocket
# only ever allows AF_UNIX. That combination blocks event-loop creation
# itself, so every test fails during fixture setup with HASocketBlockedError
# before any test code runs -- independent of what the test does.
#
# This can't be fixed by re-ordering pytest hooks: the plugin's socket
# lockdown and pytest's own fixture-setup step are both plugins registered
# before this conftest, in an order where pytest's fixture-setup always
# fires after the plugin's lockdown, regardless of hook priority markers
# used here.
#
# Instead, replace pytest_socket.disable_socket with a version that also
# permits AF_INET/AF_INET6 creation. This does not weaken test isolation:
# the plugin always calls pytest_socket.socket_allow_hosts(["127.0.0.1"])
# immediately beforehand, which patches connect()/connect_ex() to still
# reject any real outbound connection to a non-local host. Only local
# socket *creation* (needed for the self-pipe) is unblocked. Gated to
# win32 so Linux/macOS/CI keep the plugin's default, unmodified behavior.
if sys.platform == "win32":
    import socket as _socket_mod

    import pytest_socket

    # This shim reaches into pytest_socket internals; assert they exist so a
    # future version bump fails loudly here instead of breaking tests silently.
    # (pytest-socket is pinned to 0.8.0 in requirements-dev.txt.)
    _required = (
        "_true_socket",
        "disable_socket",
        "SocketBlockedError",
        "_guarded_getaddrinfo",
        "_guarded_gethostbyname",
    )
    _missing = [name for name in _required if not hasattr(pytest_socket, name)]
    assert not _missing, (
        f"pytest_socket is missing {_missing}; the Windows socket shim in "
        "conftest.py depends on pytest-socket==0.8.0 internals and needs "
        "updating for the installed version."
    )

    _TRUE_SOCKET = pytest_socket._true_socket

    def _win_compatible_disable_socket(allow_unix_socket: bool = False) -> None:
        """Like pytest_socket.disable_socket, but also allows AF_INET/AF_INET6
        creation so asyncio's Windows self-pipe (socket.socketpair()) works.
        """

        class WindowsCompatibleGuardedSocket(_TRUE_SOCKET):
            """Socket guard that additionally permits local AF_INET(6)."""

            def __new__(cls, family=-1, type=-1, proto=-1, fileno=None):
                is_unix = (
                    hasattr(_socket_mod, "AF_UNIX") and family == _socket_mod.AF_UNIX
                )
                is_inet = family in (_socket_mod.AF_INET, _socket_mod.AF_INET6)
                if (is_unix and allow_unix_socket) or is_inet:
                    return super().__new__(cls, family, type, proto, fileno)
                raise pytest_socket.SocketBlockedError()

        _socket_mod.socket = WindowsCompatibleGuardedSocket
        _socket_mod.getaddrinfo = pytest_socket._guarded_getaddrinfo
        _socket_mod.gethostbyname = pytest_socket._guarded_gethostbyname

    pytest_socket.disable_socket = _win_compatible_disable_socket
