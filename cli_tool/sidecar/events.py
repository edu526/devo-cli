"""Pydantic event models for WebSocket broadcast."""

from typing import Literal, Optional

from pydantic import BaseModel


class HelloEvent(BaseModel):
    event: Literal["hello"] = "hello"
    server_version: str
    started_at: str


class ConnectionStateEvent(BaseModel):
    event: Literal["connection.state"] = "connection.state"
    name: str
    state: str
    local_port: Optional[int] = None
    error: Optional[str] = None


class ConnectionLogEvent(BaseModel):
    event: Literal["connection.log"] = "connection.log"
    name: str
    line: str


class ProfileExpiringEvent(BaseModel):
    event: Literal["profile.expiring"] = "profile.expiring"
    name: str
    seconds_remaining: int


class ProfileRefreshedEvent(BaseModel):
    event: Literal["profile.refreshed"] = "profile.refreshed"
    names: list[str]
    success: bool


class ConfigChangedEvent(BaseModel):
    event: Literal["config.changed"] = "config.changed"
