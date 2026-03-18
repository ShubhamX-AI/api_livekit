# Livekit Architecture:

This document provides a visual-first breakdown of how AI agents integrate with Web, standard SIP (Twilio), and custom SIP (Exotel) systems.

---

## 1. Web Integration: Full AI Pipeline

This flow describes how a web client connects and how audio data flows through the AI processing stack.

### 🔄 Data Flow Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Web as 🌐 Web Browser
    participant API as 🔑 [API Server]
    participant LK as ☁️ [LiveKit Server]
    participant Agent as 🤖 [AI Agent Session]

    Note over Web, API: Phase 1: Secure Authentication
    Web->>API: GET /api/get_token?agent=bank
    Note right of API: server.py validates & generates JWT
    API-->>Web: Return Access Token (JWT)

    Note over Web, Agent: Phase 2: Session Establishment
    Web->>LK: Connect with JWT
    LK->>Agent: OnParticipantJoined
    Agent->>LK: Subscribe to Web Audio Track

    Note over Agent: Phase 3: The AI Processing Loop
    loop Continuous Streaming
        Web->>LK: User Voice (Opus)
        LK->>Agent: Audio Frame
        Agent->>Agent: 🎙️ STT (Deepgram/Whisper) ⮕ Text
        Agent->>Agent: 🧠 LLM (OpenAI/Groq) ⮕ Logic
        Agent->>Agent: 🔊 TTS (Cartesia/Sarvam) ⮕ Audio
        Agent->>LK: Agent Voice (Opus)
        LK->>Web: Hello! (Low-Latency Playback)
    end
```

---

## 2. Standard SIP Integration (Twilio/LiveKit SIP)

Native integration for phone calls using LiveKit's built-in SIP participants.

### 📞 Signaling & Media Flow

```mermaid
graph LR
    User[📱 Phone User] <-->|PSTN| Twilio[Twilio/Trunk]
    Twilio <-->|SIP/RTP| LKSIP[LiveKit SIP Participant]
    
    subgraph "LiveKit Media Room"
        LKSIP <-->|Audio Track| LK[LiveKit Room]
        Agent[🤖 AI Agent] <-->|Audio Track| LK
    end

    subgraph "Internal AI Brain"
        Agent --> STT[Speech to Text]
        STT --> LLM[Context Analysis]
        LLM --> TTS[Voice Synthesis]
        TTS --> Agent
    end

    style LKSIP fill:#f5f5f5,stroke:#333
    style Agent fill:#e1f5fe,stroke:#01579b
```

---

## 3. Custom SIP Reach (Exotel Integration)

A high-performance bridge for providers like Exotel that handles both outbound bridge setup and inbound number routing.

### 🌉 Bridge Architecture

```mermaid
graph TD
    subgraph "External Telephony"
        Exo[📞 Exotel Infrastructure]
    end

    subgraph "Custom SIP Bridge (custom_sip_reach)"
        SIP[SIP Signaling Client]
        RTP[RTP Media Bridge]
        Port[Dynamic Port Pool]
    end

    subgraph "AI Core Ecosystem"
        LKR[LiveKit Room]
        Agent[🤖 AI Agent Worker]
    end

    %% Connection Logic
    Exo -->|1. SIP INVITE| SIP
    SIP -->|2. Acquire Port| Port
    Port -.->|3. Bind UDP| RTP
    SIP -->|4. 200 OK| Exo

    %% Media Path
    Exo <-->|RTP G711 PCMU| RTP
    RTP <-->|WebRTC Track Opus| LKR
    LKR <-->|Audio| Agent

    %% Styling
    style RTP fill:#f9f,stroke:#333,stroke-width:2px
    style Agent fill:#bbf,stroke:#333,stroke-width:2px
    style SIP fill:#fff4dd,stroke:#d4a017

```

### Inbound Routing Architecture

Inbound Exotel calls do not use LiveKit's managed SIP participant. Instead, the custom bridge receives the SIP `INVITE`, normalizes the dialed number, looks up the active inbound mapping in MongoDB, creates a LiveKit room, and dispatches the mapped assistant.

### Inbound Components

- `/inbound` API routes manage the `inbound_sip` mappings.
- MongoDB stores the normalized inbound number, provider config, and attached `assistant_id`.
- The Exotel inbound bridge performs SIP signaling, RTP relay, and room setup.
- LiveKit dispatch metadata includes the inbound number and caller number for the worker session.

### Inbound Call Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Caller as 📱 Caller
    participant Exotel as 📞 Exotel
    participant Bridge as 🌉 Inbound Bridge
    participant DB as 🗄️ MongoDB
    participant LK as ☁️ LiveKit
    participant Agent as 🤖 AI Agent

    Caller->>Exotel: Dial Exotel number
    Exotel->>Bridge: SIP INVITE
    Bridge->>Bridge: Normalize dialed number
    Bridge->>DB: Lookup active inbound_sip mapping
    DB-->>Bridge: Mapping with assistant_id
    Bridge->>DB: Load active assistant
    Bridge->>LK: Create room
    Bridge->>LK: Create agent dispatch with metadata
    Bridge-->>Exotel: SIP 200 OK
    Bridge->>LK: Connect RTP bridge to room
    Bridge->>Agent: Publish call_answered event
    Exotel<-->>Bridge: RTP audio
    Bridge<-->>LK: Audio relay
    LK<-->>Agent: Real-time voice session
```

### Inbound Failure Paths

- No active mapping or detached mapping returns `480 Temporarily Unavailable`.
- Missing or inactive assistant also returns `480 Temporarily Unavailable`.
- Room creation or dispatch failure returns `500 Internal Server Error`.
- Call shutdown is handled by SIP `BYE`, LiveKit disconnect, or RTP silence timeout.
