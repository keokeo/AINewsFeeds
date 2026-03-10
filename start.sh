#!/bin/bash

# Configuration
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
VENV_DIR="${ROOT_DIR}/venv"

# Function to handle script termination
function cleanup {
    echo ""
    echo "============================================="
    echo "🛑 Shutting down backend and frontend services..."
    echo "============================================="
    kill $(jobs -p)
    exit
}

# Trap SIGINT and SIGTERM to run cleanup
trap cleanup SIGINT SIGTERM

echo "============================================="
echo "🚀 Starting AI News System"
echo "============================================="

# 1. Start Backend
echo "⏳ Starting Backend Server..."
cd "${ROOT_DIR}"
if [ -d "${VENV_DIR}" ]; then
    echo "⚡ Activating Python virtual environment..."
    source "${VENV_DIR}/bin/activate"
else
    echo "⚠️  Warning: venv not found at ${VENV_DIR}"
fi

# Run backend in the background. Note: importing backend.x requires running from ROOT_DIR
export PYTHONPATH="${ROOT_DIR}"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "✅ Backend started on http://127.0.0.0:8000"

# 2. Start Frontend
echo "⏳ Starting Frontend Server..."
cd "${FRONTEND_DIR}"
npm run dev &
FRONTEND_PID=$!
echo "✅ Frontend started"

echo "============================================="
echo "🌟 System is running! Press Ctrl+C to stop."
echo "============================================="

# Wait for both background processes
wait $BACKEND_PID $FRONTEND_PID
