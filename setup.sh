#!/bin/bash

echo "💧 CascadeAI - Installation & Startup Script"
echo "=============================================="
echo ""

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  python3 -m uvicorn backend.api:app --host 0.0.0.0 --port 8000"
echo "  2. Frontend: npm start                 (in frontend/ directory)"
echo ""
