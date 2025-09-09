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

## RL Agent
The [`agent_rl`](agent_rl) package exposes Metin2 as a minimal Gym environment.
`Metin2Env` wraps the game window and provides:

- **Action space** – discrete actions mapped to key combinations. The default set now
  includes camera rotation with ``q``/``e`` in addition to basic WASD movement.
- **Observation space** – raw RGBA frames captured from the window.
- **Info dict** – helper metrics such as current HP ratio and number of detected monsters.
- **Dynamic reset** – optional keyboard sequences can be executed at reset to
  teleport the player to a consistent starting location.

Rewards combine monster defeats, HP loss and a small time penalty, e.g.:

```
+1 per defeated monster
-ΔHP when taking damage (extra -1 on death)
-0.01 every step
```

Install [TensorBoard](https://www.tensorflow.org/tensorboard) to monitor training; it is optional but recommended.

Train an agent with [stable-baselines3](https://stable-baselines3.readthedocs.io/):

```bash
python training/train_rl_agent.py --algo dqn --total-timesteps 10000
```
The replay buffer stores both current and next observations, so memory usage is
approximately `buffer_size × H × W × 3 × dtype × 2`. With `uint8` 84×84 RGB
frames this is ~42 KB per transition (~420 MB for the default `--buffer-size
10000`). Reduce the buffer if RAM is limited, e.g.:

```bash
python training/train_rl_agent.py --algo dqn --total-timesteps 10000 --buffer-size 50000
```

TensorBoard logs and the final model are stored under `runs/rl/<algo_timestamp>/`.
The training script supports additional options:

```bash
python training/train_rl_agent.py --algo dqn --frame-stack 4 --dueling-dqn
```

`--frame-stack` wraps the environment with a frame stack for temporal context
and `--dueling-dqn` enables the dueling architecture for SB3's DQN.

For supervised pretraining from recorded sessions, a simple behaviour cloning
utility is available:

```bash
python training/train_bc.py --dataset path/to/demos.npz --epochs 10
```

Each environment step yields `(observation, reward, done, info)` where:

- `observation` – ``H×W×4`` frame array.
- `reward` – value computed from the scheme above.
- `info` – `{"hp": <0-1>, "monsters": <count>}`.

A short run (~10k steps) typically produces an average reward around **-0.2**.

## Dataset Tools
Utilities in the [`tools/`](tools) folder help build training datasets.

### Extract Frames
Save every ``n``‑th frame from gameplay recordings:
```bash
python tools/extract_frames.py --rec-dir data/recordings --out-dir datasets/mt2/images/train --step 15
```

### Label Assistant
Generate YOLO labels from model predictions.  In interactive mode press ``Y`` or ``Space`` to accept detections for an image, any other key skips it.  Use ``--skip-existing`` to ignore files that already have labels:
```bash
python tools/label_assistant.py \
  --model runs/detect/train/weights/best.pt \
  --images datasets/mt2/images/train \
  --labels datasets/mt2/labels/train \
  --confidence 0.3 \
  --interactive \
  --skip-existing
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

## Standalone Executable

PyInstaller can bundle the GUI into a single file so users do not need a separate Python installation.

1. Install development requirements (includes PyInstaller):

   ```bash
   pip install -r requirements-dev.txt
   ```

2. Build the executable:

   ```bash
   python tools/build_gui.py
   ```

The resulting file will be located in the `dist/` directory and can be distributed to end users.

## Contributing

Documentation and in‑code comments should be written in **English**. Polish
clarifications may be kept as inline comments when helpful, but the primary
docstrings and README content must remain in English.
