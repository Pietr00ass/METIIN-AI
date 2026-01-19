from __future__ import annotations

YOLO_CLASSES = [
    "metin",
    "boss",
    "mob_aggressive",
    "mob_neutral",
    "loot_label",
    "ore",
    "fish",
]

YOLO_CLASS_INDEX = {name: idx for idx, name in enumerate(YOLO_CLASSES)}

TARGET_PRIORITY = [
    "boss",
    "metin",
    "mob_aggressive",
    "mob_neutral",
    "ore",
    "fish",
    "loot_label",
]

LOOT_CLASSES = ["loot_label"]

__all__ = ["YOLO_CLASSES", "YOLO_CLASS_INDEX", "TARGET_PRIORITY", "LOOT_CLASSES"]
