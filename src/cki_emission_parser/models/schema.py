from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    nrd_path: str
    title: str
    type: str
    applies_to: list[str]
    required_evidence: bool = True
    allow_derivation: bool = False
    derivation_rule: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    preferred_documents: list[str] = Field(default_factory=list)
    date_kinds: list[str] = Field(default_factory=list)
    notes: str | None = None


class ExtractSet(BaseModel):
    version: int
    instrument_classes: list[str]
    fields: list[FieldSpec]

    def for_instrument(self, instrument_class: str) -> list[FieldSpec]:
        matched = [field for field in self.fields if instrument_class in field.applies_to]
        if matched:
            return matched
        if instrument_class == "unknown":
            return list(self.fields)
        return []


class CatalogField(BaseModel):
    name: str
    description: str | None = None
    block: str | None = None


class NrdCatalog(BaseModel):
    fields: list[CatalogField]
    by_name: dict[str, CatalogField] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self.by_name = {f.name: f for f in self.fields}
