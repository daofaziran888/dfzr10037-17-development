"""可复查子图文件与交接记录的内存仓库。

文件与交接记录是子图探查的交割产物，独立于通用业务模块表存放，
避免污染运营概览的模块统计；真实项目里会换成文件存储与数据库表。
"""
from __future__ import annotations

from typing import Any

_files: list[dict[str, Any]] = []
_handoffs: list[dict[str, Any]] = []


def next_file_id() -> int:
    return max((int(item.get("id", 0)) for item in _files), default=0) + 1


def next_handoff_id() -> int:
    return max((int(item.get("id", 0)) for item in _handoffs), default=0) + 1


def add_file(record: dict[str, Any]) -> dict[str, Any]:
    _files.append(record)
    return record


def list_files() -> list[dict[str, Any]]:
    return list(_files)


def find_file(file_id: int) -> dict[str, Any] | None:
    for item in _files:
        if int(item.get("id", 0)) == file_id:
            return item
    return None


def add_handoff(record: dict[str, Any]) -> dict[str, Any]:
    _handoffs.append(record)
    return record


def find_handoff(file_no: str) -> dict[str, Any] | None:
    """按文件编号找回交接记录：交接失败后重试时据此找回同一探查种子。"""
    for item in _handoffs:
        if item.get("文件编号") == file_no:
            return item
    return None
