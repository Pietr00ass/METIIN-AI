from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import mss
import numpy as np
import pydirectinput
import yaml
from ultralytics import YOLO


@dataclass(frozen=True)
class BotConfig:
    model_path: str
    region: tuple[int, int, int, int]
    confidence: float
    keys: dict[str, str]


def load_config(path: str | Path) -> BotConfig:
    """Load bot configuration from a YAML file."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    region = tuple(int(value) for value in data["region"])
    return BotConfig(
        model_path=str(data["model_path"]),
        region=region,
        confidence=float(data["confidence"]),
        keys=dict(data["keys"]),
    )


def _extract_detections(result) -> list[tuple[str, float]]:
    detections: list[tuple[str, float]] = []
    names = result.names
    for box in result.boxes:
        cls_id = int(box.cls)
        label = names.get(cls_id, str(cls_id))
        detections.append((label, float(box.conf)))
    return detections


def run_bot(cfg: BotConfig) -> None:
    """Run the vision bot loop."""
    model = YOLO(cfg.model_path)
    attack_key = cfg.keys.get("attack")
    loot_key = cfg.keys.get("loot")
    last_attack = 0.0
    last_loot = 0.0

    with mss.mss() as sct:
        monitor = {
            "left": cfg.region[0],
            "top": cfg.region[1],
            "width": cfg.region[2],
            "height": cfg.region[3],
        }
        while True:
            frame = np.array(sct.grab(monitor))[:, :, :3]
            result = model.predict(
                source=frame,
                verbose=False,
                conf=cfg.confidence,
            )[0]
            detections = _extract_detections(result)
            now = time.monotonic()

            if detections and attack_key and now - last_attack >= 0.4:
                pydirectinput.press(attack_key)
                last_attack = now

            if loot_key and any(label == "loot" for label, _ in detections):
                if now - last_loot >= 0.6:
                    pydirectinput.press(loot_key)
                    last_loot = now

            time.sleep(0.02)


def main() -> None:
    cfg = load_config("config.yaml")
    run_bot(cfg)


if __name__ == "__main__":
    main()
