# METIIN-AI

## Project Overview
METIIN-AI provides vision-based automation for the Metin2 game. It captures the game window, detects objects with a YOLO model and drives the character through keyboard input. The repository includes tools for recording gameplay, training YOLO models and running either a Qt GUI or lightweight agent scripts.

## Prerequisites
### Hardware
- Windows PC capable of running Metin2
- NVIDIA GPU with CUDA support for faster model training and inference (CPU is supported but slower)

### Software
- Python 3.10+
- pip for dependency management

## Dependency Installation
1. Create and activate a Python environment.
2. Install runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Model Training
YOLO models are trained with the Ultralytics API. Prepare a dataset YAML and run:
```bash
python training/train_yolo.py --data path/to/data.yaml --model yolov8n.pt --epochs 50 --imgsz 640 --batch 16 --device 0
```
The script saves results under `runs/detect/train` by default. Adjust epochs, image size or device as needed.

## Running
### GUI
Launch the control panel with real‑time preview and training utilities:
```bash
python gui/app.py
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

## Configuration and Templates
- Agent settings such as window title, detector paths and movement policy live in [`config/agent.yaml`](config/agent.yaml).
- UI templates for channel buttons, teleport pages and other elements are stored in [`assets/templates/`](assets/templates/). Use `tools/capture_template.py` to capture additional templates.
