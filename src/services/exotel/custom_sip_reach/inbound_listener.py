"""
Inbound SIP TCP listener — handles BYE and OPTIONS from Exotel.

When Exotel initiates a BYE on a *new* TCP connection (rather than the
outbound INVITE connection), this listener catches it and signals the
bridge to tear down the call.
"""

import asyncio
import multiprocessing
import multiprocessing.synchronize
import threading

from .config import EXOTEL_CUSTOMER_SIP_PORT, EXOTEL_SIP_ALLOWED_IPS, INBOUND_SIP_LISTEN
from .sip_client import ExotelSipClient
from src.core.logger import logger, setup_logging
setup_logging()

# ─────────────────────────────────────────────────────────────────────────────
# Module-level state
# ─────────────────────────────────────────────────────────────────────────────

_inbound_server: asyncio.AbstractServer | None = None
_inbound_lock = threading.Lock()
# Values are multiprocessing.Event objects (OS-level shared memory). The parent process sets
# them here when Exotel sends BYE. Each bridge subprocess receives its own event handle via
# argument — it does NOT look up this dict. The dict is only used by the inbound listener.
_call_registry: dict[str, multiprocessing.synchronize.Event] = {}
_registry_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def register_call_id(call_id: str) -> multiprocessing.synchronize.Event:
    """Register a call-ID and return a multiprocessing.Event that fires on inbound BYE."""
    event = multiprocessing.Event()
    with _registry_lock:
        _call_registry[call_id] = event
    return event


def register_call_id_with_event(call_id: str, event: multiprocessing.synchronize.Event) -> None:
    """Register a pre-created multiprocessing.Event for a call-ID.

    Used by the dispatcher when it pre-generates call_id before spawning the bridge
    subprocess, so the inbound listener can signal the subprocess on BYE.
    """
    with _registry_lock:
        _call_registry[call_id] = event


def unregister_call_id(call_id: str):
    """Remove a call-ID from the registry."""
    with _registry_lock:
        _call_registry.pop(call_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# Server lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def ensure_inbound_server():
    """Start the inbound SIP listener (once, idempotent). Must be called from the main loop."""
    global _inbound_server
    if not INBOUND_SIP_LISTEN:
        return
    with _inbound_lock:
        if _inbound_server is not None:
            return
        try:
            _inbound_server = await asyncio.start_server(
                _handle_inbound_sip, "0.0.0.0", EXOTEL_CUSTOMER_SIP_PORT
            )
            logger.info(
                "[SIP-IN] Listening on 0.0.0.0:%s",
                EXOTEL_CUSTOMER_SIP_PORT,
            )
        except Exception as e:
            logger.error(f"[SIP-IN] Failed to bind {EXOTEL_CUSTOMER_SIP_PORT}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Connection handler
# ─────────────────────────────────────────────────────────────────────────────


async def _handle_inbound_sip(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    buf = b""
    peer = writer.get_extra_info("peername")
    # Only accept SIP from known Exotel IPs (if allowlist is configured)
    if EXOTEL_SIP_ALLOWED_IPS and peer and peer[0] not in EXOTEL_SIP_ALLOWED_IPS:
        logger.warning(f"[SIP-IN] Rejected connection from untrusted IP {peer[0]}")
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            buf += data

            while b"\r\n\r\n" in buf:
                he = buf.index(b"\r\n\r\n")
                hb = buf[:he].decode(errors="replace")
                rest = buf[he + 4 :]
                lines = hb.split("\r\n")
                start = lines[0]
                hdrs = {}
                via_headers = []
                record_routes = []

                for l in lines[1:]:
                    if ":" in l:
                        k, v = l.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k == "via":
                            via_headers.append(v)
                        elif k == "record-route":
                            record_routes.append(v)
                        else:
                            hdrs[k] = v

                cl = int(hdrs.get("content-length", "0"))
                if len(rest) < cl:
                    break

                body = rest[:cl].decode(errors="replace")
                buf = rest[cl:]

                if start.startswith("BYE "):
                    call_id = hdrs.get("call-id")
                    logger.info(f"[SIP-IN] ← BYE from {peer} call-id={call_id}")
                    with _registry_lock:
                        evt = _call_registry.get(call_id)
                    if evt:
                        evt.set()
                    writer.write(ExotelSipClient._response_200_ok(hdrs, via_headers=via_headers))
                    await writer.drain()
                    logger.info("[SIP-IN] → 200 OK (BYE)")
                elif start.startswith("OPTIONS "):
                    writer.write(ExotelSipClient._response_200_ok(hdrs, via_headers=via_headers))
                    await writer.drain()
                    logger.info(f"[SIP-IN] → 200 OK (OPTIONS) from {peer}")
                elif start.startswith("INVITE "):
                    call_id = hdrs.get("call-id")
                    logger.info(f"[SIP-IN] ← INVITE from {peer} call-id={call_id}")
                    from .inbound_bridge import handle_inbound_call
                    asyncio.create_task(
                        handle_inbound_call(
                            sdp_body=body,
                            writer=writer,
                            from_header=hdrs.get("from", ""),
                            to_header=hdrs.get("to", ""),
                            call_id=call_id,
                            cseq=hdrs.get("cseq", ""),
                            via_headers=via_headers,
                            record_routes=record_routes,
                        )
                    )
                elif start.startswith("ACK "):
                    call_id = hdrs.get("call-id")
                    logger.info(f"[SIP-IN] ← ACK from {peer} call-id={call_id}")
    except Exception as e:
        logger.info(f"[SIP-IN] Connection ended: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
