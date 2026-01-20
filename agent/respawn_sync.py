from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from agent import AgentConfig, get_config
from utils.logging_config import logger


@dataclass(frozen=True)
class RespawnEvent:
    channel: int
    slot: int
    respawn_at: float
    label: str | None = None

    def seconds_until(self, now: float | None = None) -> float:
        if now is None:
            now = time.time()
        return self.respawn_at - now

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "slot": self.slot,
            "respawn_at": self.respawn_at,
            "label": self.label,
        }


class _RespawnHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        if "data-respawn-at" in attr_map or "data-respawn-in" in attr_map:
            self.events.append(attr_map)


class RespawnSync:
    """Fetch and cache respawn schedules from API or HTML sources."""

    def __init__(self, cfg: AgentConfig | dict | None = None) -> None:
        if cfg is None:
            cfg = get_config()
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.respawn_cfg = cfg.respawn
        self._cache: list[RespawnEvent] = []
        self._cache_at: float = 0.0
        self._cache_path = Path(self.respawn_cfg.cache_path)
        self._load_cache()

    def _load_cache(self) -> None:
        if not self._cache_path.exists():
            return
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._cache_at = float(payload.get("fetched_at", 0.0))
            self._cache = self._parse_cached_events(payload.get("events", []))
            logger.debug("Wczytano cache respawnów z {}", self._cache_path)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Nie udało się wczytać cache respawnów: {}", exc)

    def _save_cache(self, events: list[RespawnEvent]) -> None:
        if not self._cache_path.parent.exists():
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": time.time(), "events": [e.to_dict() for e in events]}
        try:
            self._cache_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Nie udało się zapisać cache respawnów: {}", exc)

    def _parse_cached_events(self, payload: Iterable[dict]) -> list[RespawnEvent]:
        events = []
        for item in payload:
            try:
                events.append(
                    RespawnEvent(
                        channel=int(item.get("channel")),
                        slot=int(item.get("slot")),
                        respawn_at=float(item.get("respawn_at")),
                        label=item.get("label"),
                    )
                )
            except (TypeError, ValueError):
                continue
        return events

    def fetch_schedule(self, force: bool = False) -> list[RespawnEvent]:
        if not self.respawn_cfg.enabled:
            return []
        now = time.time()
        if (
            not force
            and self._cache
            and now - self._cache_at < float(self.respawn_cfg.cache_ttl_sec)
        ):
            return list(self._cache)

        raw = self._fetch_raw()
        if raw is None:
            if self._cache:
                logger.warning("Używam cache respawnów z powodu błędu pobierania")
            return list(self._cache)

        events = self._parse_raw(raw)
        if events:
            self._cache = events
            self._cache_at = time.time()
            self._save_cache(events)
            logger.info("Zaktualizowano harmonogram respawnów ({} pozycji)", len(events))
        return list(events)

    def _fetch_raw(self) -> str | None:
        url = self.respawn_cfg.respawn_url.strip()
        if not url:
            logger.debug("Brak respawn_url w konfiguracji")
            return None
        attempts = max(1, int(self.respawn_cfg.retry_attempts))
        backoff = float(self.respawn_cfg.retry_backoff_sec)
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    return response.read().decode("utf-8")
            except (urllib.error.URLError, TimeoutError) as exc:
                logger.warning(
                    "Błąd pobierania respawnów (próba {}/{}): {}",
                    attempt + 1,
                    attempts,
                    exc,
                )
                if attempt < attempts - 1:
                    time.sleep(backoff * (2**attempt))
        return None

    def _parse_raw(self, raw: str) -> list[RespawnEvent]:
        fmt = self.respawn_cfg.format.lower()
        if fmt == "html" or self.respawn_cfg.source.lower() == "html":
            return self._parse_html(raw)
        return self._parse_json(raw)

    def _parse_html(self, raw: str) -> list[RespawnEvent]:
        parser = _RespawnHtmlParser()
        parser.feed(raw)
        events: list[RespawnEvent] = []
        now = time.time()
        for attrs in parser.events:
            try:
                channel = int(attrs.get("data-channel", attrs.get("data-ch", "0")))
                slot = int(attrs.get("data-slot", "0"))
            except ValueError:
                continue
            if channel <= 0 or slot <= 0:
                continue
            respawn_at = self._parse_time_value(
                attrs.get("data-respawn-at"),
                attrs.get("data-respawn-in"),
                now,
            )
            if respawn_at is None:
                continue
            events.append(
                RespawnEvent(
                    channel=channel,
                    slot=slot,
                    respawn_at=respawn_at,
                    label=attrs.get("data-label"),
                )
            )
        return sorted(events, key=lambda e: e.respawn_at)

    def _parse_json(self, raw: str) -> list[RespawnEvent]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Nie udało się sparsować JSON respawnów: {}", exc)
            return []

        if isinstance(payload, dict):
            items = payload.get("respawns", [])
        else:
            items = payload

        now = time.time()
        events: list[RespawnEvent] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            try:
                channel = int(item.get("channel", item.get("ch", 0)))
                slot = int(item.get("slot", 0))
            except (TypeError, ValueError):
                continue
            if channel <= 0 or slot <= 0:
                continue
            respawn_at = self._parse_time_value(
                item.get("respawn_at"),
                item.get("respawn_in_sec"),
                now,
            )
            if respawn_at is None:
                continue
            events.append(
                RespawnEvent(
                    channel=channel,
                    slot=slot,
                    respawn_at=respawn_at,
                    label=item.get("label"),
                )
            )
        return sorted(events, key=lambda e: e.respawn_at)

    def _parse_time_value(
        self,
        absolute_value: str | float | int | None,
        relative_value: str | float | int | None,
        now: float,
    ) -> float | None:
        if relative_value is not None:
            try:
                return now + float(relative_value)
            except (TypeError, ValueError):
                return None
        if absolute_value is None:
            return None
        if isinstance(absolute_value, (int, float)):
            return float(absolute_value)
        if isinstance(absolute_value, str):
            parsed = self._parse_datetime(absolute_value)
            if parsed is not None:
                return parsed
        return None

    def _parse_datetime(self, value: str) -> float | None:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return dt.timestamp()

    def next_respawn_for(self, channel: int, slot: int) -> RespawnEvent | None:
        now = time.time()
        events = self.fetch_schedule()
        upcoming = [
            e
            for e in events
            if e.channel == channel and e.slot == slot and e.respawn_at >= now
        ]
        if not upcoming:
            return None
        return min(upcoming, key=lambda e: e.respawn_at)

    def upcoming_events(self, limit: int = 10) -> list[RespawnEvent]:
        now = time.time()
        events = [e for e in self.fetch_schedule() if e.respawn_at >= now]
        return sorted(events, key=lambda e: e.respawn_at)[:limit]


__all__ = ["RespawnSync", "RespawnEvent"]
