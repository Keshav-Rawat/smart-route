# 🚦 SMART_ROUTE

> Decentralized, Adaptive, and Trustworthy Traffic Control System  
> **Built for SIH 2025 by Team Path Finders**

## 🏗️ Architecture
- **Edge AI** — YOLOv8 vehicle detection
- **Backend** — FastAPI on `localhost:8000`
- **Dashboard** — React + Vite on `localhost:5173`
- **Simulation** — SUMO adaptive signals
- **Blockchain** — Hyperledger Fabric audit logs

## 🚀 Quick Start

### Option 1: Docker (recommended)
\`\`\`bash
docker-compose up --build
\`\`\`

### Option 2: Manual
\`\`\`bash
# Backend
cd backend && pip install -r requirements.txt && python main.py

# Edge AI (new terminal)
cd edge-ai && pip install -r requirements.txt && python detector.py
\`\`\`

## 📡 Endpoints
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173

## 📁 Project Structure
\`\`\`
smart-route/
├── edge-ai/       # YOLOv8 detection
├── backend/       # FastAPI server
├── forecasting/   # LSTM prediction
├── simulation/    # SUMO traffic sim
├── blockchain/    # Hyperledger logger
├── dashboard/     # React UI
└── docs/          # Documentation
\`\`\`