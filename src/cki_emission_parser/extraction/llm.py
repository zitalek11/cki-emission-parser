from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import FieldProposal, SourceFragment
from cki_emission_parser.paths import prompts_dir

_MAX_FRAGMENT_CHARS = 1400


class LlmProvider(ABC):
    @abstractmethod
    def extract_field(
        self,
        field: FieldSpec,
        fragments: list[SourceFragment],
        *,
        instrument_class: str,
    ) -> FieldProposal:
        raise NotImplementedError


class NullLlmProvider(LlmProvider):
    def extract_field(
        self,
        field: FieldSpec,
        fragments: list[SourceFragment],
        *,
        instrument_class: str,
    ) -> FieldProposal:
        return FieldProposal(reason="LLM не задан")


class ScriptedLlmProvider(LlmProvider):
    def __init__(self, answers: dict[str, dict[str, Any] | list[dict[str, Any]]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def extract_field(
        self,
        field: FieldSpec,
        fragments: list[SourceFragment],
        *,
        instrument_class: str,
    ) -> FieldProposal:
        self.calls.append(field.id)
        payload = self.answers.get(field.id, {})
        if isinstance(payload, list):
            index = self.calls.count(field.id) - 1
            if index >= len(payload):
                return FieldProposal(reason="нет скриптового ответа для этого вызова")
            payload = payload[index]
        return FieldProposal.model_validate(payload)


class OpenAiCompatibleProvider(LlmProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec
        self.system_prompt = _load_system_prompt()

    def extract_field(
        self,
        field: FieldSpec,
        fragments: list[SourceFragment],
        *,
        instrument_class: str,
    ) -> FieldProposal:
        user = _build_user_prompt(field, fragments, instrument_class)
        raw = self._complete(user)
        data = _parse_json_object(raw)
        if data is None:
            return FieldProposal(reason="ответ модели не является JSON")
        return FieldProposal.model_validate(data)

    def _complete(self, user: str) -> str:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM недоступен: {exc}") from exc
        return payload["choices"][0]["message"]["content"]


def provider_from_env() -> LlmProvider | None:
    api_key = os.environ.get("CKI_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.environ.get("CKI_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("CKI_LLM_MODEL", "openai/gpt-4o-mini")
    return OpenAiCompatibleProvider(api_key=api_key, base_url=base_url, model=model)


def _load_system_prompt() -> str:
    path = prompts_dir() / "extraction.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "Верни JSON с полями value, evidence_source_id, quote, ambiguous, reason. "
        "Цитата обязана быть буквальным фрагментом candidate.text. "
        "Если доказательства нет — value=null."
    )


def _build_user_prompt(
    field: FieldSpec,
    fragments: list[SourceFragment],
    instrument_class: str,
) -> str:
    items = []
    for fragment in fragments:
        items.append(
            {
                "source_id": fragment.source_id,
                "document_name": fragment.document_name,
                "document_type": fragment.document_type,
                "page": fragment.page,
                "section": fragment.section,
                "text": fragment.text[:_MAX_FRAGMENT_CHARS],
            }
        )
    payload = {
        "instrument_class": instrument_class,
        "field": {
            "id": field.id,
            "title": field.title,
            "type": field.type,
            "notes": field.notes,
            "allow_derivation": field.allow_derivation,
        },
        "candidates": items,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
