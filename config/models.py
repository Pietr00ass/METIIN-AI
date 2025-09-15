"""Pydantic models describing agent configuration."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WindowConfig(BaseModel):
    title_substr: str = "Metin2"


class PathsConfig(BaseModel):
    templates_dir: str = "assets/templates"
    model: str = "runs/detect/train/weights/best.pt"
    log_dir: Optional[str] = None


class LoggingConfig(BaseModel):
    level: str = "INFO"
    retention: str = "7 days"


class KeyBindings(BaseModel):
    forward: str = "w"
    left: str = "a"
    back: str = "s"
    right: str = "d"
    rotate: str = "e"


class ControlsConfig(BaseModel):
    keys: KeyBindings = Field(default_factory=KeyBindings)
    movement: bool = True
    key_repeat_ms: int = 60
    mouse_pause: float = 0.02


class DetectorPolicy(BaseModel):
    deadzone_x: float = 0.05
    desired_box_w: float = 0.12


class DetectorConfig(BaseModel):
    classes: List[str] = Field(default_factory=lambda: ["metin", "boss", "potwory"])
    conf_thr: float = 0.5
    iou_thr: float = 0.45
    policy: DetectorPolicy = Field(default_factory=DetectorPolicy)


class StuckConfig(BaseModel):
    window: float = 0.8
    min_mag: float = 0.7
    recovery_action: str = "rotate"


class ScanConfig(BaseModel):
    enabled: bool = True
    period: float = 0.066
    key: str = "e"
    sweeps: int = 8
    sweep_ms: int = 250
    idle_sec: float = 0.0
    pause: float = 0.0


class CooldownsConfig(BaseModel):
    attack: float = 0.0


class AutoPressConfig(BaseModel):
    enabled: bool = False
    key: str = ""
    interval_sec: float = 1.0


class BuffConfig(BaseModel):
    key: str
    interval_sec: float


class TeleportSlot(BaseModel):
    page: str = "Strona I"
    slot: int


class TeleportConfig(BaseModel):
    slots: List[TeleportSlot] = Field(default_factory=list)
    page: Optional[str] = None
    page_label: Optional[str] = None
    no_target_sec: float = 10.0
    channel_every: int = 8


class ChannelConfig(BaseModel):
    settle_sec: float = 5.0
    timeout_per_ch: float = 5.0
    hotkeys: Dict[int, str] = Field(default_factory=dict)


class CycleConfig(BaseModel):
    ch_from: int = 1
    ch_to: int = 8
    slots: List[int] = Field(default_factory=lambda: list(range(1, 9)))
    per_spot_sec: float = 90
    clear_sec: float = 6
    sequence: List[Dict[str, int]] = Field(default_factory=list)


class PotionConfig(BaseModel):
    hp_key: str = ""
    hp_threshold: int = 0
    mp_key: str = ""
    mp_threshold: int = 0


class AgentConfig(BaseModel):
    strategy: str = "hunt_destroy"
    window: WindowConfig = Field(default_factory=WindowConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    controls: ControlsConfig = Field(default_factory=ControlsConfig)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    stuck: StuckConfig = Field(default_factory=StuckConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    cooldowns: CooldownsConfig = Field(default_factory=CooldownsConfig)
    auto_press: AutoPressConfig = Field(default_factory=AutoPressConfig)
    buffs: List[BuffConfig] = Field(default_factory=list)
    priority: List[str] = Field(default_factory=lambda: ["boss", "metin", "potwory"])
    teleport: TeleportConfig = Field(default_factory=TeleportConfig)
    channels: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7, 8])
    channel: ChannelConfig = Field(default_factory=ChannelConfig)
    cycle: CycleConfig = Field(default_factory=CycleConfig)
    potions: PotionConfig = Field(default_factory=PotionConfig)
    dry_run: bool = False
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


__all__ = [
    "AgentConfig",
    "WindowConfig",
    "PathsConfig",
    "ControlsConfig",
    "DetectorConfig",
    "DetectorPolicy",
    "StuckConfig",
    "ScanConfig",
    "CooldownsConfig",
    "AutoPressConfig",
    "BuffConfig",
    "TeleportConfig",
    "TeleportSlot",
    "ChannelConfig",
    "CycleConfig",
    "PotionConfig",
    "LoggingConfig",
]

