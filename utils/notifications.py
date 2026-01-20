from __future__ import annotations

from dataclasses import dataclass
import io
import json
import mimetypes
import uuid
from typing import Iterable
import urllib.request

import numpy as np
from PIL import Image

from utils.logging_config import logger


@dataclass(frozen=True)
class NotificationSettings:
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    discord_webhook: str | None = None
    include_screenshots: bool = True
    timeout_sec: float = 10.0


def image_to_png_bytes(image) -> bytes | None:
    if image is None:
        return None
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    if isinstance(image, Image.Image):
        pil_image = image
    elif hasattr(image, "rgb") and hasattr(image, "size"):
        pil_image = Image.frombytes("RGB", image.size, image.rgb)
    elif isinstance(image, np.ndarray):
        if image.ndim >= 3 and image.shape[2] >= 3:
            rgb = image[:, :, :3][:, :, ::-1]
            pil_image = Image.fromarray(rgb)
        else:
            pil_image = Image.fromarray(image)
    else:
        logger.warning("Unsupported screenshot type: {}", type(image))
        return None
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return buffer.getvalue()


def _post_json(url: str, payload: dict, timeout: float) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def _encode_multipart(
    fields: Iterable[tuple[str, str]],
    files: Iterable[dict],
    boundary: str,
) -> bytes:
    lines: list[bytes] = []
    for name, value in fields:
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode(
                "utf-8"
            )
        )
    for file in files:
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        disposition = (
            f'Content-Disposition: form-data; name="{file["name"]}"; '
            f'filename="{file["filename"]}"\r\n'
        )
        lines.append(disposition.encode("utf-8"))
        lines.append(f'Content-Type: {file["content_type"]}\r\n\r\n'.encode("utf-8"))
        lines.append(file["data"])
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines)


def _post_multipart(
    url: str,
    fields: Iterable[tuple[str, str]],
    files: Iterable[dict],
    timeout: float,
) -> None:
    boundary = uuid.uuid4().hex
    body = _encode_multipart(fields, files, boundary)
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


class NotificationsClient:
    def __init__(self, settings: NotificationSettings) -> None:
        self.settings = settings

    @classmethod
    def from_config(cls, cfg) -> "NotificationsClient":
        if cfg is None:
            return cls(NotificationSettings())
        return cls(
            NotificationSettings(
                telegram_token=getattr(cfg, "telegram_token", None) or None,
                telegram_chat_id=getattr(cfg, "telegram_chat_id", None) or None,
                discord_webhook=getattr(cfg, "discord_webhook", None) or None,
                include_screenshots=bool(
                    getattr(cfg, "include_screenshots", True)
                ),
                timeout_sec=float(getattr(cfg, "timeout_sec", 10.0)),
            )
        )

    @property
    def has_targets(self) -> bool:
        telegram_ok = bool(
            self.settings.telegram_token and self.settings.telegram_chat_id
        )
        discord_ok = bool(self.settings.discord_webhook)
        return telegram_ok or discord_ok

    def send_message(self, text: str) -> None:
        if not text or not self.has_targets:
            return
        if self.settings.telegram_token and self.settings.telegram_chat_id:
            url = (
                "https://api.telegram.org/bot"
                f"{self.settings.telegram_token}/sendMessage"
            )
            payload = {
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
            }
            try:
                _post_json(url, payload, self.settings.timeout_sec)
            except Exception:  # pragma: no cover - network best effort
                logger.opt(exception=True).warning("Failed to send Telegram message")
        if self.settings.discord_webhook:
            payload = {"content": text}
            try:
                _post_json(self.settings.discord_webhook, payload, self.settings.timeout_sec)
            except Exception:  # pragma: no cover - network best effort
                logger.opt(exception=True).warning("Failed to send Discord message")

    def send_screenshot(self, png_bytes: bytes, caption: str | None = None) -> None:
        if not png_bytes or not self.has_targets or not self.settings.include_screenshots:
            return
        filename = "screenshot.png"
        content_type = mimetypes.guess_type(filename)[0] or "image/png"
        if self.settings.telegram_token and self.settings.telegram_chat_id:
            url = (
                "https://api.telegram.org/bot"
                f"{self.settings.telegram_token}/sendPhoto"
            )
            fields = [("chat_id", self.settings.telegram_chat_id)]
            if caption:
                fields.append(("caption", caption))
            files = [
                {
                    "name": "photo",
                    "filename": filename,
                    "content_type": content_type,
                    "data": png_bytes,
                }
            ]
            try:
                _post_multipart(url, fields, files, self.settings.timeout_sec)
            except Exception:  # pragma: no cover - network best effort
                logger.opt(exception=True).warning("Failed to send Telegram screenshot")
        if self.settings.discord_webhook:
            payload = {"content": caption or ""}
            fields = [
                ("payload_json", json.dumps(payload)),
            ]
            files = [
                {
                    "name": "file",
                    "filename": filename,
                    "content_type": content_type,
                    "data": png_bytes,
                }
            ]
            try:
                _post_multipart(self.settings.discord_webhook, fields, files, self.settings.timeout_sec)
            except Exception:  # pragma: no cover - network best effort
                logger.opt(exception=True).warning("Failed to send Discord screenshot")


__all__ = [
    "NotificationSettings",
    "NotificationsClient",
    "image_to_png_bytes",
]
