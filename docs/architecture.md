# System Architecture

The LiveKit Agents API consists of several key components working together to facilitate real-time AI conversations.

## High-Level Overview

```mermaid
graph TD
    Client[Client App] -->|Connect| LiveKit[LiveKit Server]
    Client -->|REST API| API[API Server (FastAPI)]
    
    API -->|Manage| DB[(MongoDB)]
    
    Worker[Agent Worker] -->|Connect| LiveKit
    Worker -->|Fetch Context| DB
    
    LiveKit <-->|WebRTC| Client
    LiveKit <-->|WebRTC| Worker
```

## Components

### 1. API Server (`server_run.py`)

- Built with **FastAPI**.
- Manages sessions, users, and agent configurations.
- Exposes REST endpoints for creating tokens, managing assistants, and retrieving history.
- Stores state in MongoDB.

### 2. Agent Worker (`src/worker.py`)

- Runs the actual AI logic.
- Connects to LiveKit rooms as a participant.
- Listens to audio events, transcribes speech, generates responses (LLM), and synthesizes speech (TTS).
- Executes "Tools" (function calls) when requested by the LLM.

### 3. Database Layer

- **MongoDB**: Stores:
  - `Sessions`: Metadata about active and past conversations.
  - `Assistants`: Configuration for different agent personas.
  - `Tools`: Definitions of available tools.
