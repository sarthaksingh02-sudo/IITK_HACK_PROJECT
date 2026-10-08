#!/usr/bin/env bash
# AccessAI Demo Launcher (Linux / macOS)
# Usage: ./run_demo.sh  OR  make demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  AccessAI — AVINYA 2K26 (IIT Kanpur) Demo Launcher"
echo "  Offline-First AI for Rural Welfare & Opportunities"
echo "=========================================================="

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[setup] .env created from .env.example"
fi

mkdir -p keys packets

if [ ! -f "keys/private.key" ]; then
    echo "[setup] Generating Ed25519 keypair..."
    python3 -c "
import nacl.signing, pathlib
sk = nacl.signing.SigningKey.generate()
pathlib.Path('keys/private.key').write_bytes(bytes(sk))
pathlib.Path('keys/public.key').write_bytes(bytes(sk.verify_key))
print('[setup] Ed25519 Keypair generated.')
"
fi

echo "[setup] Seeding databases from real notices & personas..."
python3 cloud/seed.py
python3 hub/seed.py

echo "[setup] Signing and broadcasting official notice packets..."
python3 cloud/publish_sample.py --approve-all

echo ""
echo "=========================================================="
echo "  📡 Cloud Control Center → http://localhost:8000"
echo "  🏛️ Village Hub PWA      → http://localhost:8001"
echo "=========================================================="
echo ""

python3 -m uvicorn cloud.main:app --port 8000 &
CLOUD_PID=$!
python3 -m uvicorn hub.main:app --port 8001 &
HUB_PID=$!

echo "[demo] Services started (Cloud PID: $CLOUD_PID, Hub PID: $HUB_PID)"
echo "Press Ctrl+C to terminate both services."

trap "kill $CLOUD_PID $HUB_PID 2>/dev/null || true" EXIT
wait
