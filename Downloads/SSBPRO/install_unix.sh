#!/usr/bin/env bash
echo "==============================================="
echo "  LeanTraderBot Mini v4 - Linux/Mac Installer"
echo "==============================================="

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Installation complete!"
echo "Run demo:"
echo "    ./start_demo.sh"
echo ""
echo "Run live trading:"
echo "    ./start_live.sh"
echo ""
