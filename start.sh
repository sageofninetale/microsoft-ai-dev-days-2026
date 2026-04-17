#!/bin/bash
# CascadeAI - Start both servers
# Run this from Mac Terminal (not VS Code): bash start.sh

PROJECT_DIR="$HOME/Desktop/microsoft/microsoft-ai-dev-days-2026"
cd "$PROJECT_DIR"

echo "🧹 Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:3001 | xargs kill -9 2>/dev/null
pkill -f "python backend/main" 2>/dev/null
pkill -f "react-scripts" 2>/dev/null
sleep 2

echo ""
echo "🚀 Starting backend on port 8000..."
PYTHONPATH="$PROJECT_DIR" /usr/local/bin/python3 -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 > /tmp/cascade-backend.log 2>&1 &
BACKEND_PID=$!
disown $BACKEND_PID
echo "   Backend PID: $BACKEND_PID (disowned - won't be suspended)"

echo "⏳ Waiting for backend..."
sleep 5

# Verify backend
if curl -s http://localhost:8000/api/nurses > /dev/null 2>&1; then
    echo "   ✅ Backend is UP"
else
    echo "   ❌ Backend failed! Check: cat /tmp/cascade-backend.log"
    exit 1
fi

echo ""
echo "🚀 Starting frontend on port 3000..."
cd "$PROJECT_DIR/frontend"
npm start > /tmp/cascade-frontend.log 2>&1 &
FRONTEND_PID=$!
disown $FRONTEND_PID
echo "   Frontend PID: $FRONTEND_PID (disowned - won't be suspended)"

echo ""
echo "⏳ Waiting for frontend to compile (~20s)..."
sleep 20

echo ""
echo "============================================"
echo "✅ CascadeAI is running!"
echo "   App:     http://localhost:3000/app"
echo "   Backend: http://localhost:8000/api/nurses"
echo "   Logs:    tail -f /tmp/cascade-backend.log"
echo "            tail -f /tmp/cascade-frontend.log"
echo "============================================"
echo ""
echo "⚠️  Keep THIS terminal open. Press Ctrl+C to stop everything."
echo ""

# Keep script alive so processes don't get orphaned
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
