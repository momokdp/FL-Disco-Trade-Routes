#!/bin/bash
cd "$(dirname "$0")"
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo "Starting FL Trade Routes server on http://localhost:8000"
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
