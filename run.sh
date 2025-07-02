#!/bin/bash

cleanup() {
    echo -e "\nCaught SIGINT! Shutting down..."
    if [ -n "$(jobs -p)" ]; then
        kill $(jobs -p)
    fi
    echo "All processes terminated."
    exit 0
}

trap cleanup INT

echo "Starting Python backend server on port 8000 (with reload) in conda env 'pipecat'..."
(cd aurora-python && conda run -n pipecat uvicorn app:app --reload) &
BACKEND_PID=$!

echo "Starting Next.js frontend server on port 3000..."
(cd aurora-frontend && npm run dev) &
FRONTEND_PID=$!

echo -e "\nBackend running with PID: $BACKEND_PID"
echo "Frontend running with PID: $FRONTEND_PID"
echo -e "\nBoth servers are running. Press Ctrl+C to stop both."

wait
