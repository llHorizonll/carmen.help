# Carmen.help - AI Help Desk Assistant

A seamless, human-like help desk assistant for Carmen Cloud that reduces support tickets by providing instant, accurate documentation lookups.

## Table of Contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [AWS EC2 Deployment](#aws-ec2-deployment)
- [Docker Deployment](#docker-deployment)

---

## Architecture

### Multi-Agent System (Manager-Worker Pattern)

| Agent | Role | Description |
|-------|------|-------------|
| **Librarian** | Documentation Agent | Searches vector database for relevant documentation |
| **Expert** | Technical Support Agent | Synthesizes step-by-step guides from retrieved docs |
| **Executor** | WebApp Task Agent | Generates JSON payloads or CLI commands for actions |
| **Validator** | Quality Guard Agent | Reviews responses for accuracy and hallucination detection |

### Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + TypeScript + @chatui/core |
| Backend | FastAPI (Python 3.10+) |
| LLM | Z.ai GLM-4.7 (OpenAI-compatible API) |
| Vector DB | ChromaDB |
| Embeddings | HuggingFace all-MiniLM-L6-v2 |

---

## Requirements

### Backend Requirements

- **Python**: 3.10 or higher
- **pip**: Latest version recommended
- **Git**: For cloning documentation repository

### Frontend Requirements

- **Node.js**: 18.x or higher
- **npm**: 9.x or higher (comes with Node.js)

### Optional

- **Docker** & **Docker Compose**: For containerized deployment

---

## Installation

### Step 1: Clone the Project

```bash
git clone <repository-url>
cd carmen.help
```

### Step 2: Environment Configuration

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Z.ai API Configuration (Required)
ZAI_API_KEY=your_zai_api_key_here
ZAI_API_BASE=https://api.z.ai/api/coding/paas/v4
ZAI_MODEL=glm-4.7

# Vector Database
CHROMA_PERSIST_DIR=./data/chroma

# Documentation Source
DOCS_REPO_URL=https://github.com/llHorizonll/docscarmencloud.git

# Embedding Configuration
EMBEDDING_PROVIDER=huggingface
HUGGINGFACE_MODEL=all-MiniLM-L6-v2

# Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:5173

# Documentation Site (for citations)
DOCS_SITE_URL=https://docscarmencloud.vercel.app
```

---

## Backend Setup

### Step 1: Create Virtual Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Dependencies installed:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `openai` - Z.ai API client (OpenAI-compatible)
- `chromadb` - Vector database
- `sentence-transformers` - Embeddings
- `pydantic-settings` - Configuration management
- `httpx` - Async HTTP client
- `python-dotenv` - Environment variables

### Step 3: Initialize Knowledge Base

```bash
# Clone Carmen Cloud documentation
python -m knowledge_base.sync_docs

# Parse markdown files, generate embeddings, and index to ChromaDB
python -m knowledge_base.index_docs -v
```

### Step 4: Verify Installation

```bash
# Check vector store stats
python -m knowledge_base.vector_store --action stats

# Test search functionality
python -m knowledge_base.vector_store --action search --query "billing"
```

### Step 5: Start Backend Server

```bash
# Development mode (with auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Backend will be available at:** `http://localhost:8000`

**API Documentation:** `http://localhost:8000/docs`

---

## Frontend Setup

### Step 1: Install Node Dependencies

```bash
cd frontend

# Install dependencies
npm install
```

**Dependencies installed:**
- `react` - UI library
- `react-dom` - React DOM rendering
- `@chatui/core` - Chat UI components
- `typescript` - Type checking
- `vite` - Build tool

### Step 2: Configure API Endpoint

The frontend is pre-configured to proxy API requests to `http://localhost:8000`. If your backend runs on a different port, edit `vite.config.ts`:

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // Change if needed
        changeOrigin: true,
      },
    },
  },
});
```

### Step 3: Start Development Server

```bash
# Start development server
npm run dev
```

**Frontend will be available at:** `http://localhost:5173`

### Step 4: Build for Production

```bash
# Create production build
npm run build

# Preview production build
npm run preview
```

Production files will be in the `dist/` folder.

---

## Running the Application

### Development Mode

Open **two terminal windows**:

**Terminal 1 - Backend:**
```bash
cd backend
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
uvicorn main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

---

## Project Structure

```
carmen.help/
├── backend/
│   ├── agents/                    # Multi-Agent System
│   │   ├── __init__.py
│   │   ├── agent_types.py         # Type definitions
│   │   ├── prompts.py             # System prompts for all agents
│   │   ├── orchestrator.py        # Manager-Worker coordinator
│   │   └── validator.py           # Hallucination detection
│   │
│   ├── api/                       # API Endpoints
│   │   ├── __init__.py
│   │   ├── chat.py                # Chat endpoint (streaming)
│   │   └── rag.py                 # RAG retrieval logic
│   │
│   ├── knowledge_base/            # RAG Pipeline
│   │   ├── __init__.py
│   │   ├── sync_docs.py           # Clone docs from GitHub
│   │   ├── parser.py              # Parse Markdown by headers
│   │   ├── embeddings.py          # Generate embeddings
│   │   ├── vector_store.py        # ChromaDB operations
│   │   ├── index_docs.py          # Index docs to vector DB
│   │   └── docs_repo/             # Cloned documentation
│   │
│   ├── services/                  # External Services
│   │   ├── __init__.py
│   │   ├── llm.py                 # Z.ai LLM integration
│   │   └── retriever.py           # Vector DB search
│   │
│   ├── config.py                  # Configuration settings
│   ├── main.py                    # FastAPI application
│   ├── requirements.txt           # Python dependencies
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Main chat application
│   │   └── main.tsx               # React entry point
│   │
│   ├── index.html                 # HTML template
│   ├── package.json               # Node dependencies
│   ├── tsconfig.json              # TypeScript config
│   ├── vite.config.ts             # Vite configuration
│   ├── nginx.conf                 # Nginx config (production)
│   └── Dockerfile
│
├── data/                          # Generated data (gitignored)
│   ├── docs/                      # Cloned documentation
│   └── chroma/                    # Vector database
│
├── .env.example                   # Environment template
├── .gitignore
├── docker-compose.yml             # Docker composition
└── README.md
```

---

## API Reference

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "Carmen.help API",
  "version": "0.1.0"
}
```

### Chat Endpoint

```bash
POST /api/chat/
Content-Type: application/json

{
  "message": "How do I set up billing?",
  "stream": false
}
```

Response:
```json
{
  "answer": "To set up billing in Carmen Cloud...",
  "sources": [
    {
      "id": "billing-setup",
      "source_url": "https://docscarmencloud.vercel.app/billing",
      "score": 0.89
    }
  ]
}
```

### Get Suggestions

```bash
GET /api/chat/suggestions
```

Response:
```json
{
  "suggestions": [
    "How do I set up billing?",
    "What is the site policy?",
    "How do I create a new project?"
  ]
}
```

---

## AWS EC2 Deployment

### Step 1: Launch EC2 Instance

1. Go to AWS Console → EC2 → Launch Instance
2. Choose **Ubuntu Server 22.04 LTS** (or Amazon Linux 2023)
3. Instance type: **t3.medium** (minimum 2 vCPU, 4GB RAM)
4. Configure Security Group:
   | Type | Port | Source |
   |------|------|--------|
   | SSH | 22 | Your IP |
   | HTTP | 80 | 0.0.0.0/0 |
   | HTTPS | 443 | 0.0.0.0/0 |
   | Custom TCP | 8000 | 0.0.0.0/0 |

5. Create or select a key pair for SSH access
6. Launch the instance

### Step 2: Connect and Install Dependencies

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Git and Nginx
sudo apt install -y git nginx

# Verify installations
python3.11 --version
node --version
npm --version
```

### Step 3: Clone and Setup Project

```bash
# Clone project
cd /home/ubuntu
git clone <your-repository-url> carmen.help
cd carmen.help

# Create .env file
nano .env
# Add your configuration (ZAI_API_KEY, etc.)
```

### Step 4: Setup Backend

```bash
cd /home/ubuntu/carmen.help/backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize knowledge base
python -m knowledge_base.sync_docs
python -m knowledge_base.index_docs -v

# Test backend
uvicorn main:app --host 0.0.0.0 --port 8000
# Press Ctrl+C after testing
```

### Step 5: Setup Frontend

```bash
cd /home/ubuntu/carmen.help/frontend

# Install dependencies
npm install

# Build for production
npm run build
```

### Step 6: Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/carmen.help
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Or use EC2 public IP

    # Frontend (static files)
    location / {
        root /home/ubuntu/carmen.help/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

Enable the site:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/carmen.help /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Step 7: Setup Systemd Service for Backend

```bash
# Create systemd service file
sudo nano /etc/systemd/system/carmen-backend.service
```

Add this configuration:

```ini
[Unit]
Description=Carmen.help Backend API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/carmen.help/backend
Environment="PATH=/home/ubuntu/carmen.help/backend/venv/bin"
EnvironmentFile=/home/ubuntu/carmen.help/.env
ExecStart=/home/ubuntu/carmen.help/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable carmen-backend

# Start the service
sudo systemctl start carmen-backend

# Check status
sudo systemctl status carmen-backend

# View logs
sudo journalctl -u carmen-backend -f
```

### Step 8: Setup SSL with Let's Encrypt (Optional)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
sudo certbot renew --dry-run
```

### Step 9: Verify Deployment

```bash
# Check backend health
curl http://localhost:8000/health

# Check Nginx is serving frontend
curl http://localhost

# Test from external (use EC2 public IP or domain)
curl http://your-ec2-public-ip/health
```

### Maintenance Commands

```bash
# Restart backend
sudo systemctl restart carmen-backend

# View backend logs
sudo journalctl -u carmen-backend -f

# Update application
cd /home/ubuntu/carmen.help
git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install && npm run build
sudo systemctl restart carmen-backend
sudo systemctl restart nginx

# Re-index documentation
cd /home/ubuntu/carmen.help/backend
source venv/bin/activate
python -m knowledge_base.sync_docs
python -m knowledge_base.index_docs -v
sudo systemctl restart carmen-backend
```

### EC2 Cost Optimization

| Instance Type | vCPU | RAM | Monthly Cost (On-Demand) |
|--------------|------|-----|--------------------------|
| t3.micro | 2 | 1 GB | ~$8/month (free tier eligible) |
| t3.small | 2 | 2 GB | ~$15/month |
| t3.medium | 2 | 4 GB | ~$30/month (recommended) |

**Tips:**
- Use Spot Instances for 60-70% savings
- Use Reserved Instances for 30-40% savings on long-term
- Enable auto-scaling for high traffic

---

## Docker Deployment

### Build and Run with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Access Points (Docker)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |

### Build Individual Images

```bash
# Build backend
docker build -t carmen-backend ./backend

# Build frontend
docker build -t carmen-frontend ./frontend

# Run backend
docker run -p 8000:8000 --env-file .env carmen-backend

# Run frontend
docker run -p 5173:80 carmen-frontend
```

---

## Troubleshooting

### Backend Issues

**Error: `ModuleNotFoundError`**
```bash
# Ensure virtual environment is activated
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**Error: `ChromaDB connection failed`**
```bash
# Ensure data directory exists
mkdir -p data/chroma
```

**Error: `Z.ai API key not found`**
```bash
# Check .env file has ZAI_API_KEY set
cat .env | grep ZAI_API_KEY
```

**Alternative LLM Providers (Free Options):**

If you prefer a free LLM provider, you can use Groq or OpenRouter:

```env
# Groq (Free, Fast)
ZAI_API_KEY=gsk_your_groq_key
ZAI_API_BASE=https://api.groq.com/openai/v1
ZAI_MODEL=llama-3.3-70b-versatile

# OpenRouter (Free Models Available)
ZAI_API_KEY=sk-or-your_key
ZAI_API_BASE=https://openrouter.ai/api/v1
ZAI_MODEL=z-ai/glm-4.5-air:free
```

### Frontend Issues

**Error: `npm install` fails**
```bash
# Clear npm cache and retry
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

**Error: API requests return 404**
```bash
# Ensure backend is running on port 8000
curl http://localhost:8000/health
```

---

## Features

- **Auto-Suggest**: 3 common questions displayed on chat open
- **Source Citations**: Every answer includes links to docscarmencloud.vercel.app
- **Multi-Agent**: Librarian → Expert → Executor → Validator pipeline
- **Hallucination Detection**: Validator checks responses against source docs
- **Streaming**: Real-time response streaming (SSE)
- **Code Blocks**: Syntax highlighted with copy button

---

## License

MIT License - See [LICENSE](LICENSE) for details.
