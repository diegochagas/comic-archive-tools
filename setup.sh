#!/usr/bin/env bash
# One-time setup: creates the Python venv and downloads the text-detection model.
set -euo pipefail
cd "$(dirname "$0")"

MODEL_URL="https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/comictextdetector.pt.onnx"
MODEL_PATH="models/comictextdetector.pt.onnx"

if [ ! -d venv ]; then
    echo "Creating venv..."
    python3 -m venv venv
    venv/bin/pip install --quiet --upgrade pip
fi
venv/bin/pip install --quiet onnxruntime opencv-python-headless numpy \
    pillow pymupdf "psd-tools[composite]"
echo "venv ready: $(venv/bin/python -c 'import onnxruntime; print("onnxruntime", onnxruntime.__version__)')"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Downloading text-detection model (~95 MB)..."
    mkdir -p models
    curl -L --fail -o "$MODEL_PATH" "$MODEL_URL"
fi
echo "model ready: $MODEL_PATH"

if ! flatpak info org.gimp.GIMP >/dev/null 2>&1; then
    echo "WARNING: flatpak GIMP (org.gimp.GIMP) not found - install it to use this skill."
    echo "  flatpak install flathub org.gimp.GIMP"
fi

if command -v npm >/dev/null 2>&1; then
    npm install --silent
    echo "node_modules ready: ag-psd $(node -p "require('./node_modules/ag-psd/package.json').version")"
else
    echo "WARNING: npm not found - install Node.js to enable add_text_layers.mjs (Photoshop text-layer step)."
fi

echo "Setup complete."
