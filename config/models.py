from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class WindowConfig(BaseModel):
    title_substr: str = "Metin2"


class PathsConfig(BaseModel):
    templates_dir: str = "assets/templates"
    model: str = "runs/detect/train/weights/best.pt"
    log_dir: Optional[str] = "logs"


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
    keys: KeyBindings = KeyBindings()
    movement: bool = True
    key_repeat_ms: int = 60
    mouse_pause: float = 0.02


class HumanizerConfig(BaseModel):
    pause_jitter: float = 0.05
    cursor_jitter: float = 2.0


class DetectorPolicy(BaseModel):
    deadzone_x: float = 0.05
    desired_box_w: float = 0.12


class DetectorConfig(BaseModel):
    classes: List[str] = ["metin", "boss", "potwory"]
    conf_thr: float = 0.5
    iou_thr: float = 0.45
    policy: DetectorPolicy = DetectorPolicy()


class StuckConfig(BaseModel):
    window: float = 0.8
    min_mag: float = 0.7
    recovery_action: str = "rotate"


class ScanConfig(BaseModel):
    period: float = 0.066
    key: str = "e"
    sweeps: int = 8
    sweep_ms: int = 250


class CooldownsConfig(BaseModel):
    pass


class AutoPressConfig(BaseModel):
    enabled: bool = False
    key: str = "f1"
    interval_sec: float = 60.0


class BuffConfig(BaseModel):
    key: str = "f1"
    interval_sec: float = 60.0


class TeleportSlot(BaseModel):
    page: str = "Strona I"
    slot: int = 1


class TeleportConfig(BaseModel):
    slots: List[TeleportSlot] = []
    no_target_sec: float = 10.0
    channel_every: int = 8
    click_duration: float = 0.05
    open_panel_delay: float = 0.0
    row_click_delay: float = 0.0
    after_load_delay: float = 0.0


class ChannelConfig(BaseModel):
    settle_sec: float = 5.0
    timeout_per_ch: float = 5.0


class CycleConfig(BaseModel):
    ch_from: int = 1
    ch_to: int = 8
    slots: List[int] = list(range(1, 9))
    per_spot_sec: float = 90
    clear_sec: float = 6
    sequence: List[Dict[str, int]] = []


class AgentConfig(BaseModel):
    strategy: str = "hunt_destroy"
    window: WindowConfig = WindowConfig()
    paths: PathsConfig = PathsConfig()
    controls: ControlsConfig = ControlsConfig()
    humanizer: HumanizerConfig = HumanizerConfig()
    detector: DetectorConfig = DetectorConfig()
    stuck: StuckConfig = StuckConfig()
    scan: ScanConfig = ScanConfig()
    cooldowns: CooldownsConfig = CooldownsConfig()
    auto_press: AutoPressConfig = AutoPressConfig()
    buffs: List[BuffConfig] = []
    priority: List[str] = ["boss", "metin", "potwory"]
    teleport: TeleportConfig = TeleportConfig()
    channels: List[int] = [1, 2, 3, 4, 5, 6, 7, 8]
    channel: ChannelConfig = ChannelConfig()
    cycle: CycleConfig = CycleConfig()
    dry_run: bool = False
    logging: LoggingConfig = LoggingConfig()


__all__ = [
    "AgentConfig",
    "WindowConfig",
    "PathsConfig",
    "ControlsConfig",
    "HumanizerConfig",
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
    "LoggingConfig",
]
