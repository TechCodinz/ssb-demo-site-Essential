#!/usr/bin/env bash
# Prepare a clean release folder: ensure only config.sample.json exists by default
rm -f config.json
cp config.sample.json config.json
echo "Release prepared. Edit config.json with RPC & PRIVATE_KEY before running live."

#(Make executable: chmod +x MAKE_RELEASE.sh)