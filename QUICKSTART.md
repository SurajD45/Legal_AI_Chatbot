# 🚀 Quick Start Guide - Legal AI Assistant

## ⏱️ Get Running in 5 Minutes

### Step 1: Prerequisites

```bash
# Check you have Docker installed
docker --version
docker-compose --version

# If not installed, get Docker Desktop:
# Windows/Mac: https://www.docker.com/products/docker-desktop
# Linux: https://docs.docker.com/engine/install/
```

### Step 2: Clone & Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd legal-ai-assistant

# Copy environment template
cp .env.example .env

# Edit .env and add your Groq API key
# Get free API key from: https://console.groq.com/keys
nano .env  # or use any text editor
```

**Important**: Replace `your_groq_api_key_here` with your actual Groq API key in the `.env` file.

### Step 3: Start Services

```bash
# Start all services (Qdrant + Backend + Frontend)
docker-compose up -d

# Wait for services to be healthy (~30 seconds)
# Watch the logs:
docker-compose logs -f backend
```

### Step 4: Index Data (One-Time Setup)

```bash
# Index IPC sections into Qdrant
docker-compose exec backend python scripts/index_data.py

# You should see:
# ✅ Successfully indexed 512 IPC sections!
```

### Step 5: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

## ✅ Verify Installation

```bash
# Test backend health
curl http://localhost:8000/health

# Test a query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Section 302?"}'
```

## 🎉 That's It!

Your Legal AI Assistant is now running. Try asking questions like:

- "What is Section 302?"
- "Explain Section 420 in simple terms"
- "What are the punishments for theft?"
- "Tell me about defamation laws"

---

## 🛑 Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove all data (including Qdrant database)
docker-compose down -v
```

---

## 🆘 Common Issues

### Port Already in Use

If you see "port is already allocated":

```bash
# Change ports in docker-compose.yml
# For example, change 8000:8000 to 8001:8000
```

### Groq API Error

If you see "Invalid API key":

1. Get a new key from https://console.groq.com/keys
2. Update `.env` file
3. Restart: `docker-compose restart backend`

### Collection Not Found

If you see "Collection not found":

```bash
# Re-run indexing
docker-compose exec backend python scripts/index_data.py
```

---

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the API at http://localhost:8000/docs
- Customize settings in `.env` file
- Add your own IPC data to `data/ipc.json`

---

**Need Help?** Check the [Troubleshooting](README.md#-troubleshooting) section in README.md
