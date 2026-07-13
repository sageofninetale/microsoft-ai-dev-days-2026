#!/bin/bash
# CascadeAI - Start both servers
# Run this from Mac Terminal (not VS Code): bash start.sh

PROJECT_DIR="$HOME/Desktop/microsoft/microsoft-ai-dev-days-2026"
GUIDELINE_MCP_DIR="$HOME/Documents/nhs-guideline-mcp"
cd "$PROJECT_DIR"

echo "🧹 Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:3001 | xargs kill -9 2>/dev/null
lsof -ti:8420 | xargs kill -9 2>/dev/null
pkill -f "python backend/main" 2>/dev/null
pkill -f "react-scripts" 2>/dev/null
sleep 2

echo ""
echo "🚀 Starting guideline MCP server on port 8420..."
# Standalone drug-interaction guideline search server (RAG + MCP), lives outside
# this repo — see ~/Documents/nhs-guideline-mcp/. draft_generator.py fails soft
# if this isn't up (safety alerts just lose their source citations), so it's
# started first but a failure here does not block backend/frontend startup.
if [ -x "$GUIDELINE_MCP_DIR/.venv/bin/python3" ]; then
    (cd "$GUIDELINE_MCP_DIR" && "$GUIDELINE_MCP_DIR/.venv/bin/python3" server.py > /tmp/cascade-guideline-mcp.log 2>&1 &)
    sleep 7
    if lsof -ti:8420 > /dev/null 2>&1; then
        echo "   ✅ Guideline MCP server is UP"
    else
        echo "   ⚠️  Guideline MCP server failed to start — drug-interaction alerts will have no source citations. Check: cat /tmp/cascade-guideline-mcp.log"
    fi
else
    echo "   ⚠️  $GUIDELINE_MCP_DIR/.venv not found — skipping. Drug-interaction alerts will have no source citations."
fi

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
echo "   App:          http://localhost:3000/app"
echo "   Backend:      http://localhost:8000/api/nurses"
echo "   Guideline MCP: http://localhost:8420/mcp"
echo "   Logs:    tail -f /tmp/cascade-backend.log"
echo "            tail -f /tmp/cascade-frontend.log"
echo "            tail -f /tmp/cascade-guideline-mcp.log"
echo "============================================"
echo ""
echo "⚠️  Keep THIS terminal open. Press Ctrl+C to stop everything."
echo ""

# Keep script alive so processes don't get orphaned. The guideline MCP server
# was started detached (not disowned into a captured PID), so it's stopped by
# port on exit rather than by PID like the other two.
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; lsof -ti:8420 | xargs kill -9 2>/dev/null; exit" INT TERM
wait
