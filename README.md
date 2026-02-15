# LiveKit Agent Service

A production-ready service for deploying real-time AI voice agents using LiveKit, OpenAI Realtime API, and Cartesia/Sarvam TTS. This service provides a REST API for managing assistants, tools, SIP trunks, and triggering outbound calls, along with a robust agent worker for handling real-time interactions.

## 🚀 Features

- **Real-time AI Agents**: Powered by OpenAI Realtime API (GPT-4o) and Cartesia/Sarvam TTS.
- **SIP Support**: Create and manage SIP outbound trunks (Twilio/Exotel) for telephony integration.
- **Outbound Calls**: Trigger programmatic outbound calls to phone numbers (currently supporting Twilio).
- **Dynamic Assistants**: Create and configure assistants with custom prompts, typed TTS configuration (Cartesia/Sarvam), and start instructions.
- **Custom Tools**: Extend assistant capabilities with custom tools (Webhooks, Static Responses) that can be attached/detached dynamically.
- **Call Recording**: Automatic call recording with LiveKit Egress to AWS S3.
- **Transcripts**: Real-time transcription storage in MongoDB.
- **Webhooks**: Automatic webhook notifications for call completion with detailed analytics.
- **Secure API**: API Key authentication for all management endpoints.

## 🛠️ Tech Stack

- **Framework**: FastAPI (Python 3.12+)
- **Real-time Communication**: LiveKit
- **Database**: MongoDB (with Beanie ODM)
- **AI/LLM**: OpenAI Realtime API
- **TTS**: Cartesia (Sonic-3) & Sarvam (Bulbul:v3)
- **Deployment**: Docker & Docker Compose

## 🏗️ Architecture

1. **API Service**: Manages resources (Assistants, API Keys, Trunks) and triggers calls.
2. **Agent Worker**: Connects to LiveKit rooms to handle AI logic (STT, LLM, TTS).
3. **LiveKit Server**: Handles real-time audio/video transport.
4. **MongoDB**: Stores configuration (assistants, tools), call records, and transcripts.
5. **Webhooks**: Pushes call data to external services upon completion.

## 📋 Prerequisites

- Docker & Docker Compose
- LiveKit Server (Cloud or Self-hosted)
- MongoDB Instance
- API Keys:
  - OpenAI API Key
  - Cartesia API Key
  - Sarvam API Key
  - LiveKit API Key & Secret
  - AWS S3 Credentials (for recordings)

## 🔧 Development Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd api_livekit
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory:

   ```ini
   # Server Configuration
   PORT=8000

   # MongoDB
   MONGODB_URL=mongodb://admin:secretpassword@localhost:27017
   DATABASE_NAME=livekit_db

   # LiveKit
   LIVEKIT_URL=wss://<your-livekit-domain>
   LIVEKIT_API_KEY=<your-api-key>
   LIVEKIT_API_SECRET=<your-api-secret>

   # AI Providers
   OPENAI_API_KEY=<your-openai-key>
   CARTESIA_API_KEY=<your-cartesia-key>
   SARVAM_API_KEY=<your-sarvam-key>

   # SMTP Configuration (for emails)
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=<your-smtp-password>
   FROM_EMAIL=noreply@yourdomain.com
   FROM_NAME="Your App Name"

   # AWS S3 (for recordings)
   AWS_ACCESS_KEY_ID=<your-access-key>
   AWS_SECRET_ACCESS_KEY=<your-secret-key>
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=<your-bucket-name>

   # Backend Configuration
   BACKEND_URL=http://localhost:8000
   ```

3. **Run with Docker Compose**:

   ```bash
   docker-compose up --build
   ```

   This will start both the API service and the Agent Worker.

## 📖 Documentation

For full API documentation, please visit: [https://api-livekit-vyom.indusnettechnologies.com/](https://api-livekit-vyom.indusnettechnologies.com/)

## 🧩 Agent Logic

The agent (`src/core/agents/session.py`):

1. Connects to the LiveKit room.
2. Fetches the assistant configuration from MongoDB using the `assistant_id` (derived from room name).
3. Injects `metadata` values into the prompt and start instruction.
4. Loads and attaches configured tools (webhooks/static) to the assistant.
5. Initializes OpenAI Realtime API and Cartesia/Sarvam TTS (based on typed configuration).
6. Listens for `transcription` events and saves them to MongoDB.
7. Triggers the `end_call` webhook upon participant disconnection.

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

## 📄 License

[MIT License](LICENSE)
