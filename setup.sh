#!/bin/bash

echo "🏥 MedReconcile - Installation & Startup Script"
echo "================================================"
echo ""

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  python -m backend.api     (in root directory)"
echo "  2. Frontend: npm start                 (in frontend/ directory)"
echo ""
