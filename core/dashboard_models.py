from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime


def _serialize_json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_json(item) for item in value]
    return value


class _CompatDataclass:
    def model_dump(self) -> dict:
        return asdict(self)

    def model_dump_json(self) -> str:
        return json.dumps(_serialize_json(asdict(self)), ensure_ascii=False)

    @classmethod
    def model_validate(cls, data):
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            return cls(**data)
        raise TypeError(f"Unsupported payload for {cls.__name__}: {type(data)!r}")

    @classmethod
    def model_validate_json(cls, json_str: str):
        data = json.loads(json_str)
        for field_name in ("custom_start_date", "custom_end_date", "date"):
            raw = data.get(field_name)
            if isinstance(raw, str) and raw:
                try:
                    data[field_name] = datetime.fromisoformat(raw)
                except ValueError:
                    pass
        return cls.model_validate(data)


@dataclass(slots=True)
class KPIData(_CompatDataclass):
    name: str
    current_value: float
    previous_value: float | None = None

    @property
    def change_percentage(self) -> float:
        if self.previous_value is None or self.previous_value == 0:
            return 0.0
        return ((self.current_value - self.previous_value) / self.previous_value) * 100

    @property
    def trend_direction(self) -> str:
        if self.previous_value is None:
            return "neutral"
        if self.current_value > self.previous_value:
            return "up"
        if self.current_value < self.previous_value:
            return "down"
        return "neutral"


@dataclass(slots=True)
class CashFlowEntry(_CompatDataclass):
    date: datetime
    inflow: float = 0.0
    outflow: float = 0.0

    @property
    def net_flow(self) -> float:
        return self.inflow - self.outflow


@dataclass(slots=True)
class DashboardSettings(_CompatDataclass):
    auto_refresh_enabled: bool = True
    auto_refresh_interval: int = 30
    selected_period: str = "this_month"
    custom_start_date: datetime | None = None
    custom_end_date: datetime | None = None
