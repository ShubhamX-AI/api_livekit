# LiveKit Agents API Documentation

---

## Build Real-Time Voice AI Agents in Minutes

A production-ready backend for deploying AI-powered voice agents with LiveKit, OpenAI, and enterprise-grade telephony integration.

[Get Started](getting-started.md){ .md-button .md-button--primary }
[View API Reference](api/authentication.md){ .md-button }

---

## :material-chart-timeline: Architecture Overview

```mermaid
graph TD
    Client[Client Application] -->|REST API| API[API Server<br/>FastAPI]
    Client -->|WebSocket| LiveKit[LiveKit Server]
    
    API -->|CRUD| DB[(MongoDB)]
    
    Worker[Agent Worker] -->|Connect| LiveKit
    Worker -->|Fetch Config| DB
    Worker -->|STT/TTS| AI[OpenAI + TTS]
    
    Worker -->|Webhook| External[External Services]
```

For detailed architecture information, see the [Architecture](architecture.md) page.

---

**Ready to build?** [Start with the Getting Started guide :octicons-arrow-right-24:](getting-started.md)
