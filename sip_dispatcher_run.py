"""
Dedicated process for two singleton services:
  - Inbound SIP listener  (Exotel BYE / OPTIONS on port 5070)
  - Outbound call dispatcher (polls MongoDB queue, drips calls)

Runs as a separate container so the api container can safely scale to
multiple workers without port-binding conflicts or duplicate dispatchers.

Note: notify_dispatcher() signals are in-memory and don't cross container
boundaries. The dispatcher falls back to its 5-second poll, so outbound
calls are dispatched within ~30s of being queued.
"""

import asyncio
import signal
import sys

from src.core.logger import setup_logging, logger
from src.core.db.database import init_db, close_db
from src.services.exotel.custom_sip_reach.inbound_listener import ensure_inbound_server
from src.services.outbound_dispatcher import outbound_dispatcher_loop

setup_logging()


async def main():
    await init_db()
    logger.info("sip_dispatcher: DB connected")

    await ensure_inbound_server()

    # dispatcher_loop runs until cancelled
    dispatcher_task = asyncio.create_task(outbound_dispatcher_loop())

    # Graceful shutdown on SIGTERM / SIGINT (Docker stop sends SIGTERM)
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set_result, sig)

    sig_received = await stop
    logger.info(f"sip_dispatcher: received {signal.Signals(sig_received).name}, shutting down")

    dispatcher_task.cancel()
    try:
        await dispatcher_task
    except asyncio.CancelledError:
        pass

    await close_db()
    logger.info("sip_dispatcher: clean shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
