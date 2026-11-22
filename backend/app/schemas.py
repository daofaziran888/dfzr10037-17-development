"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None


class SaveAsPayload(BaseModel):
    """另存可复查子图文件：可选指定选中邻边，缺省取种子在扩展深度内的全部生效邻边。"""

    edges: list[str] | None = None


class EvolvePayload(BaseModel):
    """现图演化：按新关系规则移除旧边、新增新边，图代递进一代。"""

    remove: list[str] = Field(default_factory=list)
    add: list[dict[str, str]] = Field(default_factory=list)
    reason: str = ""
