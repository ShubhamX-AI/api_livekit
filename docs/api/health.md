# Health Check

## Overview

One probe of every dependency an API request needs. Each dependency is pinged concurrently and
reported on its own, so a broken database shows up here instead of as failed calls.

!!! warning "Always HTTP 200 — read `data.status`"
    The endpoint answers `200` even when every dependency is down. A degraded dependency is
    reported in the body, never as a `5xx`, so a MongoDB or LiveKit blip cannot get every API
    container pulled out of a load balancer at once. Alert on `data.status == "degraded"`, not on
    the status code.

## Endpoint

- **URL**: `/health`
- **Method**: `GET`
- **Authentication**: Not required

## Request

No parameters or request body.

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | `true` when every check passed. Mirrors `data.status`. |
| `message` | string | `ok` or `degraded`. |
| `data.status` | string | `ok` when every check passed, otherwise `degraded`. |
| `data.version` | string | Platform version (same as the changelog and OpenAPI `info.version`). |
| `data.uptime_s` | number | Seconds since this API process started. A small value on every poll means it is crash-looping. |
| `data.checks.<name>.ok` | boolean | Whether that dependency answered. |
| `data.checks.<name>.latency_ms` | number | Round-trip time of the probe. |
| `data.checks.<name>.error` | string | Only on failure: error type and message, with secrets redacted. |

### Checks

| Name | What is probed |
| :--- | :--- |
| `mongodb` | `ping` command on the API's MongoDB client |
| `livekit` | An authenticated `ListRooms` call to the LiveKit server, so a wrong `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` fails it too |

Check names are part of the contract — dashboards key off them.

Each probe has its own deadline, `HEALTH_PROBE_TIMEOUT_S` (default `3` seconds). A probe that
does not answer in time fails with `TimeoutError`; the endpoint itself still answers.

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Always. Read `data.status`. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/health"
```

## Example Responses

Healthy:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "ok",
    "version": "1.6.0",
    "uptime_s": 5321.4,
    "checks": {
      "mongodb": { "ok": true, "latency_ms": 1.8 },
      "livekit": { "ok": true, "latency_ms": 12.6 }
    }
  }
}
```

Degraded:

```json
{
  "success": false,
  "message": "degraded",
  "data": {
    "status": "degraded",
    "version": "1.6.0",
    "uptime_s": 5340.1,
    "checks": {
      "mongodb": { "ok": true, "latency_ms": 2.0 },
      "livekit": { "ok": false, "latency_ms": 3001.5, "error": "TimeoutError" }
    }
  }
}
```
