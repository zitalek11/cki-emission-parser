from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GoldLabel = Literal["accepted", "must-be-empty", "known-bad"]


class GoldField(BaseModel):
    """Ожидание по одному полю. Эталонный Excel сам по себе не является истиной."""

    model_config = ConfigDict(extra="ignore")

    field: str
    label: GoldLabel
    value: Any | None = None
    quote_contains: str | None = None
    reason: str | None = None
    slice: str | None = None
    requires_llm: bool = False


class GoldCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    description: str | None = None
    slice: str | None = None
    fields: list[GoldField] = Field(default_factory=list)


class GoldPack(BaseModel):
    """Эталон одного комплекта. match — фрагмент пути, не имя эмитента в коде."""

    model_config = ConfigDict(extra="ignore")

    id: str
    match: str | None = None
    instrument_class: str | None = None
    slice: str | None = None
    fields: list[GoldField] = Field(default_factory=list)
    cases: list[GoldCase] = Field(default_factory=list)


class GoldFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = 1
    notes: str | None = None
    fields: list[GoldField] = Field(default_factory=list)
    cases: list[GoldCase] = Field(default_factory=list)
    packs: list[GoldPack] = Field(default_factory=list)

    def all_fields(self) -> list[GoldField]:
        items = list(self.fields)
        items.extend(_fields_from_cases(self.cases))
        return items

    def fields_for(
        self,
        *,
        pack_path: str | None = None,
        pack_id: str | None = None,
    ) -> list[GoldField]:
        if not self.packs:
            return self.all_fields()
        path_s = (pack_path or "").replace("\\", "/")
        selected = [
            pack
            for pack in self.packs
            if (pack_id and pack.id == pack_id) or (pack.match and pack.match in path_s)
        ]
        if not selected:
            return self.all_fields() if not pack_path else []
        items: list[GoldField] = []
        for pack in selected:
            for spec in pack.fields:
                items.append(_with_slice(spec, pack.slice))
            items.extend(_fields_from_cases(pack.cases, default_slice=pack.slice))
        return items


def _with_slice(spec: GoldField, default_slice: str | None) -> GoldField:
    if spec.slice or not default_slice:
        return spec
    return spec.model_copy(update={"slice": default_slice})


def _fields_from_cases(
    cases: list[GoldCase],
    *,
    default_slice: str | None = None,
) -> list[GoldField]:
    items: list[GoldField] = []
    for case in cases:
        inherited = case.slice or default_slice
        for spec in case.fields:
            items.append(_with_slice(spec, inherited))
    return items

