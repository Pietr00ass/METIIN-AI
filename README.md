# METIIN-AI

## Project Overview
METIIN-AI provides vision-based automation for the Metin2 game. It captures the game window, detects objects with a YOLO model and drives the character through keyboard input. The repository includes tools for recording gameplay, training YOLO models and running either a Qt GUI or lightweight agent scripts.  The project is developed primarily on Windows but most components also run under Linux.

## Prerequisites
### Hardware
- Windows PC capable of running Metin2
- NVIDIA GPU with CUDA support for faster model training and inference (CPU is supported but slower)

### Software
- Python 3.10+
- ``pip`` for dependency management
- On Windows the [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) are required by the ``pywin32`` package.

## Dependency Installation
1. Create and activate a Python environment.
   ```bash
   python -m venv .venv
   # PowerShell
   .venv\Scripts\activate
   # or on Linux / macOS
   source .venv/bin/activate
   ```
2. Install runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   or using [Poetry](https://python-poetry.org/) for an isolated environment:
   ```bash
   poetry install
   ```
3. (Optional) Install GPU versions of ``torch``/``torchvision`` to speed up training and inference.

## Model Training
YOLO models are trained with the Ultralytics API. Prepare a dataset YAML and run:
```bash
python training/train_yolo.py --data path/to/data.yaml --model yolov8n.pt --epochs 50 --imgsz 640 --batch 16 --device 0
```
The script saves results under `runs/detect/train` by default. Adjust epochs, image size or device as needed.

## Dataset Tools
Utilities in the [`tools/`](tools) folder help build training datasets.

### Extract Frames
Save every ``n``‑th frame from gameplay recordings:
```bash
python tools/extract_frames.py --rec-dir data/recordings --out-dir datasets/mt2/images/train --step 15
```

### Label Assistant
Generate YOLO labels from model predictions.  In interactive mode press ``Y`` or ``Space`` to accept detections for an image, any other key skips it:
```bash
python tools/label_assistant.py \
  --model runs/detect/train/weights/best.pt \
  --images datasets/mt2/images/train \
  --labels datasets/mt2/labels/train \
  --confidence 0.3 \
  --interactive
```

## Running
### GUI
Launch the control panel with real‑time preview and training utilities:
```bash
python -m gui.app
```

### Headless Agent
Use the sample configuration and run a basic WASD agent:
```bash
python - <<'PY'
import yaml
from agent.infer_wasd import WasdVisionAgent
cfg = yaml.safe_load(open('config/agent.yaml'))
WasdVisionAgent(cfg).run()
PY
```

## Configuration
All runtime options live in [`config/agent.yaml`](config/agent.yaml).  Key fields include:

- **window.title_substr** – fragment of the Metin2 window title used to locate it.
- **paths.model** – path to the trained YOLO weights.
- **controls.keys** – mapping of movement/rotation keys.
- **scan** – settings for scanning the area by rotating the camera (key, number and duration of sweeps).

The file ships with sensible defaults; copy it and adjust values for your setup.  Missing entries fall back to built‑in defaults.

### Templates
UI templates for channel buttons, teleport pages and other elements are stored in [`assets/templates/`](assets/templates/). Use `tools/capture_template.py` to capture additional templates, e.g.::

    python tools/capture_template.py --roi 1000 80 90 30 --name wczytaj
Template matching logic that uses these assets lives in [`agent/template_matcher.py`](agent/template_matcher.py).

## Recording Input

`recorder/capture.py` logs mouse clicks and raw keyboard scan codes. The
keyboard listener relies on a low‑level hook provided by the
[`keyboard`](https://github.com/boppreh/keyboard) package.

* **Windows** – uses the native `SetWindowsHookEx` API through the library.
* **Linux** – reads events from `/dev/input`; this normally requires root
  privileges and may not function under Wayland compositors.
* **macOS** – only partially supported and may need additional accessibility
  permissions.

If the hook cannot be installed only mouse clicks will be recorded.

## Contributing

Documentation and in‑code comments should be written in **English**. Polish
clarifications may be kept as inline comments when helpful, but the primary
docstrings and README content must remain in English.
