from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import FieldProposal, SourceFragment
from cki_emission_parser.paths import prompts_dir

_MAX_FRAGMENT_CHARS = 1400
_MOEX_DEFAULT_URL = "https://api-new.ai.moex.com/v1"
_MOEX_DEFAULT_MODEL = "strong"
_OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"


class LlmRequestError(RuntimeError):
    """Ошибка HTTP к шлюзу модели: без traceback в CLI."""


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
        timeout_sec: int = 90,
    ) -> None:
        self.api_key = api_key
        self.base_url = normalize_base_url(base_url)
        self.model = resolve_model(self.base_url, model)
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

    def ping(self) -> str:
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 80,
            "messages": [{"role": "user", "content": "Ответь одним словом: ping"}],
        }
        return self._post(body)

    def list_models(self) -> dict[str, Any] | list[Any] | None:
        url = f"{self.base_url}/models"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError:
            return None

    def _complete(self, user: str) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": int(os.environ.get("CKI_LLM_MAX_TOKENS", "800")),
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user},
            ],
        }
        if _want_json_object(self.base_url):
            body["response_format"] = {"type": "json_object"}
        try:
            return self._post(body)
        except RuntimeError:
            if "response_format" not in body:
                raise
            body.pop("response_format", None)
            return self._post(body)

    def _post(self, body: dict[str, Any]) -> str:
        url = f"{self.base_url}/chat/completions"
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
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise LlmRequestError(_http_error_message(exc.code, url, body.get("model"), detail)) from exc
        except urllib.error.URLError as exc:
            raise LlmRequestError(f"LLM недоступен {url}: {exc}") from exc
        message = payload["choices"][0]["message"]
        content = message.get("content")
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item) for item in content
            )
        return str(content or "")


def provider_from_env() -> LlmProvider | None:
    api_key = os.environ.get("CKI_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = normalize_base_url(os.environ.get("CKI_LLM_BASE_URL") or _MOEX_DEFAULT_URL)
    model = resolve_model(base_url, os.environ.get("CKI_LLM_MODEL"))
    timeout_sec = int(os.environ.get("CKI_LLM_TIMEOUT", "90"))
    return OpenAiCompatibleProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_sec=timeout_sec,
    )


def normalize_base_url(url: str) -> str:
    text = (url or "").strip().rstrip("/")
    if not text:
        return _MOEX_DEFAULT_URL
    lowered = text.lower()
    for suffix in ("/chat/completions", "/completions"):
        if lowered.endswith(suffix):
            text = text[: -len(suffix)].rstrip("/")
            break
    parsed = urlparse(text if "://" in text else f"https://{text}")
    if "moex.com" not in (parsed.netloc or text).lower():
        return text.rstrip("/")
    path = (parsed.path or "").rstrip("/")
    if path in {"", "/"}:
        return f"{parsed.scheme}://{parsed.netloc}/v1"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def resolve_model(base_url: str, model: str | None) -> str:
    name = (model or "").strip()
    if "moex.com" in base_url.lower():
        if not name or "/" in name:
            return _MOEX_DEFAULT_MODEL
        return name
    return name or _OPENROUTER_DEFAULT_MODEL


def _http_error_message(code: int, url: str, model: Any, detail: str) -> str:
    hint = ""
    if code == 404:
        hint = (
            " Для шлюза MOEX в CKI_LLM_MODEL нужен ID модели (например strong), "
            "а CKI_LLM_BASE_URL — https://api-new.ai.moex.com/v1 без /chat/completions."
        )
    return f"LLM HTTP {code} {url} model={model}: {detail}.{hint}"


def _want_json_object(base_url: str) -> bool:
    flag = os.environ.get("CKI_LLM_JSON_OBJECT")
    if flag is not None:
        return flag.strip().lower() in {"1", "true", "yes"}
    return "moex.com" not in base_url.lower()


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
