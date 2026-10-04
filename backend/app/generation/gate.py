"""LLMGate: one generation at a time on the CPU, FIFO waiters that see their queue position change."""

import asyncio
from collections.abc import AsyncGenerator


class GateFull(RuntimeError):
    """More than max_queue requests are already waiting."""


class Ticket:
    """A place in the gate's queue; position 0 holds the gate. Release exactly when done (idempotent)."""

    def __init__(self, gate: "LLMGate") -> None:
        self._gate = gate
        self._moved = asyncio.Event()

    @property
    def position(self) -> int:
        """0 while holding the gate, n while n tickets are ahead."""
        return self._gate.index(self)

    async def positions(self) -> AsyncGenerator[int, None]:
        """Yield the current position and every change of it, ending after 0 (the gate is then held)."""
        while True:
            self._moved.clear()
            position = self.position
            yield position
            if position == 0:
                return
            await self._moved.wait()

    def notify(self) -> None:
        """Wake positions(): someone ahead left."""
        self._moved.set()

    def release(self) -> None:
        """Leave the queue (or free the gate); later tickets move up."""
        self._gate.leave(self)


class LLMGate:
    """FIFO queue whose head holds the gate; at most max_queue tickets wait behind it."""

    def __init__(self, max_queue: int) -> None:
        self._max_queue = max_queue
        self._queue: list[Ticket] = []

    def enter(self) -> Ticket:
        """Join the queue; raises GateFull if max_queue tickets are already waiting."""
        if self.waiting >= self._max_queue and self._queue:
            raise GateFull(f"{self.waiting} requests are already waiting")
        ticket = Ticket(self)
        self._queue.append(ticket)
        return ticket

    def index(self, ticket: Ticket) -> int:
        """Position of a queued ticket."""
        return self._queue.index(ticket)

    def leave(self, ticket: Ticket) -> None:
        """Remove ticket if still queued and notify the tickets behind it."""
        if ticket not in self._queue:
            return
        start = self._queue.index(ticket)
        self._queue.remove(ticket)
        for behind in self._queue[start:]:
            behind.notify()

    @property
    def active(self) -> int:
        """1 while a generation holds the gate, else 0."""
        return min(1, len(self._queue))

    @property
    def waiting(self) -> int:
        """Tickets queued behind the holder."""
        return max(0, len(self._queue) - 1)
