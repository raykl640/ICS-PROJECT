import asyncio
import socket

import httpx
import pytest
from pytest_socket import SocketBlockedError

pytestmark = pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")


def test_inet_socket_is_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_http_client_cannot_reach_network() -> None:
    with pytest.raises(SocketBlockedError):
        httpx.get("http://127.0.0.1:11434/api/tags")


def test_event_loop_still_works() -> None:
    async def answer() -> int:
        return 42

    assert asyncio.run(answer()) == 42
