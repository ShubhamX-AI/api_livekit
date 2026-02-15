# Getting Started

## Prerequisites

- **Python 3.10+** or **Docker**
- **LiveKit Server** (Cloud or Self-hosted)
- **MongoDB** (for session storage)
- API Keys for necessary services (OpenAI, Cartesia, etc.)

## Installation

### Local Development

1. **Clone the repository:**

   ```bash
   git clone https://github.com/ShubhamX-AI/api_livekit.git
   cd api_livekit
   ```

2. **Install dependencies:**
   Using `uv` (recommended):

   ```bash
   uv sync
   ```

   Or standard pip:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.local` to `.env` and fill in your keys:

   ```bash
   cp .env.local .env
   ```

4. **Run the Server:**

   ```bash
   python server_run.py
   ```

### Docker Deployment

1. **Build and Run:**

   ```bash
   docker-compose up --build
   ```

## Next Steps

- Explore the [Architecture](architecture.md) to understand the system.
- Check out [Tool Usage](api/tools.md) to add functionality.
