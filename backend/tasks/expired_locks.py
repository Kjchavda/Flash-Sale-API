"""
Expired-lock reaper — run as a background task or cron job.

Usage (as an APScheduler job in main.py):
    from backend.tasks import reap_expired_locks
    scheduler.add_job(reap_expired_locks, "interval", minutes=1)

Usage (as a standalone script):
    python -m backend.tasks
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import update

from backend.database import AsyncSessionLocal
from backend.models import Ticket, TicketStatus


async def reap_expired_locks() -> int:
    """
    Set any LOCKED ticket whose locked_until has passed back to AVAILABLE.
    Returns the number of tickets released.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Ticket)
            .where(
                Ticket.status == TicketStatus.LOCKED,
                Ticket.locked_until < now,
            )
            .values(
                status=TicketStatus.AVAILABLE,
                locked_by=None,
                locked_until=None,
            )
            # execution_options keeps this as one UPDATE statement — no ORM overhead
            .execution_options(synchronize_session=False)
        )
        await db.commit()

    released = result.rowcount  # type: ignore
    if released:
        print(f"[reaper] Released {released} expired lock(s).")
    return released


if __name__ == "__main__":
    asyncio.run(reap_expired_locks())