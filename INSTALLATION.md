# 🛠️ Installation Guide

## Quick Fix for Docker Build Timeout

If you're seeing timeout errors when building with Docker, it's because PyTorch is downloading large CUDA libraries. Here's how to fix it:

### Solution 1: Build with CPU-only PyTorch (Recommended)

The Dockerfile is already configured to use CPU-only PyTorch which is much smaller and faster to download.

```bash
# Just rebuild
docker-compose up --build -d
```

If it still times out, try:

```bash
# Increase Docker timeout
DOCKER_BUILDKIT=0 docker-compose build --build-arg BUILDKIT_INLINE_CACHE=1
docker-compose up -d
```

---

### Solution 2: Local Installation (No Docker)

If Docker keeps timing out, run locally instead:

#### Step 1: Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install PyTorch CPU-only (much smaller)
pip install torch==2.1.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
pip install -r requirements.txt
```

#### Step 2: Start Qdrant

```bash
# Run Qdrant in Docker
docker run -d -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  --name qdrant \
  qdrant/qdrant
```

#### Step 3: Configure Environment

```bash
# Make sure .env has correct settings
# QDRANT_HOST should be "localhost" for local dev
nano .env
```

Change this line:
```
QDRANT_HOST=localhost
```

#### Step 4: Index Data

```bash
python scripts/index_data.py
```

#### Step 5: Run Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 6: Run Frontend (in another terminal)

```bash
cd frontend
npm install
npm run dev
```

---

### Solution 3: Use Pre-built Docker Image (Future)

Once you have a working build, you can push it to Docker Hub and reuse it:

```bash
# Build once
docker build -t yourusername/legal-ai-backend .

# Push to Docker Hub
docker push yourusername/legal-ai-backend

# Use in docker-compose.yml
# Change: build: .
# To: image: yourusername/legal-ai-backend
```

---

## Network Issues?

If you have slow/unstable internet:

### Option A: Increase pip timeout

```bash
# In Dockerfile, change the pip install line to:
RUN pip install --no-cache-dir --timeout=1000 -r requirements.txt
```

### Option B: Use pip cache

Build with cache:

```bash
docker-compose build --build-arg PIP_NO_CACHE_DIR=0
```

---

## System Requirements

### For Docker:
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space
- **Internet**: Stable connection for initial download

### For Local:
- **Python**: 3.11+
- **RAM**: 4GB minimum (embedding model needs ~2GB)
- **Disk**: 5GB free space

---

## After Installation

1. **Verify backend**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Index data**:
   ```bash
   # With Docker:
   docker-compose exec backend python scripts/index_data.py

   # Locally:
   python scripts/index_data.py
   ```

3. **Access frontend**: http://localhost:3000

---

## Still Having Issues?

### Check Docker resources:
- Docker Desktop → Settings → Resources
- Increase CPU: 4 cores
- Increase Memory: 4GB+

### Check network:
```bash
# Test download speed
curl -o /dev/null https://files.pythonhosted.org/packages/test.tar.gz
```

### Alternative: Build on another machine
- Build on a machine with better internet
- Export the image: `docker save -o backend.tar legal-ai-backend`
- Copy to your machine
- Import: `docker load -i backend.tar`

---

**Need more help?** Open an issue on GitHub or check the troubleshooting section in README.md
