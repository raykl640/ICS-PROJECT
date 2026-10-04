"""LLMGate: one holder at a time, FIFO waiters with live positions, bounded queue, idempotent release."""

import asyncio

import pytest

from backend.app.generation.gate import GateFull, LLMGate, Ticket


async def _positions(ticket: Ticket, seen: list[int]) -> None:
    async for position in ticket.positions():
        seen.append(position)


def test_first_ticket_holds_the_gate_immediately() -> None:
    async def scenario() -> list[int]:
        gate = LLMGate(max_queue=2)
        seen: list[int] = []
        await _positions(gate.enter(), seen)
        return seen

    assert asyncio.run(scenario()) == [0]


def test_waiters_move_up_in_fifo_order() -> None:
    async def scenario() -> None:
        gate = LLMGate(max_queue=2)
        first, second, third = gate.enter(), gate.enter(), gate.enter()
        assert (gate.active, gate.waiting) == (1, 2)
        seen_second: list[int] = []
        seen_third: list[int] = []
        task_second = asyncio.create_task(_positions(second, seen_second))
        task_third = asyncio.create_task(_positions(third, seen_third))
        await asyncio.sleep(0)
        assert (seen_second, seen_third) == ([1], [2])
        first.release()
        await task_second
        assert seen_second == [1, 0]
        await asyncio.sleep(0)
        assert seen_third == [2, 1]
        second.release()
        await task_third
        assert seen_third == [2, 1, 0]

    asyncio.run(scenario())


def test_leaving_waiter_only_moves_those_behind() -> None:
    async def scenario() -> None:
        gate = LLMGate(max_queue=3)
        holder, ahead, leaving, behind = gate.enter(), gate.enter(), gate.enter(), gate.enter()
        seen_ahead: list[int] = []
        seen_behind: list[int] = []
        tasks = [asyncio.create_task(_positions(t, s)) for t, s in ((ahead, seen_ahead), (behind, seen_behind))]
        await asyncio.sleep(0)
        leaving.release()
        await asyncio.sleep(0)
        assert (seen_ahead, seen_behind) == ([1], [3, 2])
        holder.release()
        await tasks[0]
        ahead.release()
        await tasks[1]
        assert (seen_ahead, seen_behind) == ([1, 0], [3, 2, 1, 0])

    asyncio.run(scenario())


def test_full_queue_raises_and_release_is_idempotent() -> None:
    gate = LLMGate(max_queue=1)
    holder, _waiter = gate.enter(), gate.enter()
    with pytest.raises(GateFull):
        gate.enter()
    holder.release()
    holder.release()
    assert (gate.active, gate.waiting) == (1, 0)
    gate.enter()
