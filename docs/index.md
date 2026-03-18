# LiveKit Agents API Documentation

## Overview

A production-ready backend for building and operating real-time voice AI agents with LiveKit, OpenAI, and SIP telephony integration.

[Get Started](getting-started.md){ .md-button .md-button--primary }
[API Reference](api/authentication.md){ .md-button }

## Platform Summary

```mermaid
graph TD
    Client[Client Application] -->|REST API| API[API Server\nFastAPI]
    Client -->|WebRTC| LiveKit[LiveKit Server]

    API -->|CRUD| DB[(MongoDB)]

    Worker[Agent Worker] -->|Connect| LiveKit
    Worker -->|Fetch Config| DB
    Worker -->|LLM + TTS| AI[OpenAI + TTS Providers]
    Worker -->|Webhook| External[External Services]
```

See [Architecture](architecture.md) for full call-flow diagrams and integration modes.
