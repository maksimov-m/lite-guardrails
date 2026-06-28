"""LiteLLM custom guardrail для интеграции сервиса lite-guardrails.

Подключается в LiteLLM Proxy как кастомный guardrail. Сам гуард остаётся
ОТДЕЛЬНЫМ HTTP-сервисом (FastAPI + админка + БД): middleware только ходит к
нему по сети, поэтому правила/словари редактируются в админке, а не в коде
прокси, и подхватываются на лету.

Действие по КАЖДОМУ модулю настраивается независимо (в config.yaml или env):

    pii_action       anonymize | block | log | off     (default: anonymize)
    nsfw_action      block | log | off                 (default: block)
    relevant_action  block | log | off                 (default: block)

  • anonymize — PII заменяется на теги через /anonymize перед отправкой в LLM,
    а в ответе модели теги возвращаются обратно через /deanonymize. Реальные
    данные в LLM не уходят, пользователь видит оригинальные значения.
  • block     — при срабатывании запрос/ответ отклоняется (HTTP 400).
  • log       — пропускаем, но прогон фиксируется в логах гуарда.
  • off       — модуль не используется.

Проверяется и вход (async_pre_call_hook), и выход (async_post_call_success_hook).
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from litellm.caching.dual_cache import DualCache
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth

try:  # логгер прокси, если доступен
    from litellm._logging import verbose_proxy_logger as _log
except Exception:  # pragma: no cover
    import logging

    _log = logging.getLogger("lite_guardrails")

# Разделитель для склейки нескольких сообщений в один вызов /anonymize:
# PII-регулярки (email/url/phone) его не трогают, поэтому сквозная нумерация
# тегов (<EMAIL_1>...) остаётся консистентной, и после анонимизации текст
# можно разрезать обратно по этому же маркеру.
_SEP = "\n␞\n"
_META_PII_ID = "lite_guardrails_pii_id"  # куда кладём id маппинга между хуками


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class LiteGuardrails(CustomGuardrail):
    def __init__(
        self,
        guard_base_url: Optional[str] = None,
        pii_action: Optional[str] = None,
        nsfw_action: Optional[str] = None,
        relevant_action: Optional[str] = None,
        check_input: Optional[bool] = None,
        check_output: Optional[bool] = None,
        fail_closed: Optional[bool] = None,
        timeout: float = 5.0,
        **kwargs: Any,
    ):
        # приоритет: config.yaml (litellm_params) -> env -> дефолт
        self.base_url = (
            guard_base_url or os.getenv("GUARD_BASE_URL", "http://localhost:8000")
        ).rstrip("/")
        self.pii_action = (pii_action or os.getenv("GUARD_PII_ACTION", "anonymize")).lower()
        self.nsfw_action = (nsfw_action or os.getenv("GUARD_NSFW_ACTION", "block")).lower()
        self.relevant_action = (
            relevant_action or os.getenv("GUARD_RELEVANT_ACTION", "block")
        ).lower()
        self.check_input = (
            check_input if check_input is not None else _env_bool("GUARD_CHECK_INPUT", True)
        )
        self.check_output = (
            check_output if check_output is not None else _env_bool("GUARD_CHECK_OUTPUT", True)
        )
        # fail_closed: если гуард недоступен — рубить запрос (True) или пропускать (False)
        self.fail_closed = (
            fail_closed if fail_closed is not None else _env_bool("GUARD_FAIL_CLOSED", False)
        )
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        super().__init__(**kwargs)

    # ------------------------------------------------------------------ #
    # HTTP к сервису гуарда
    # ------------------------------------------------------------------ #
    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _detect(self, module: str, text: str, meta: dict) -> dict:
        r = await self._http.post(
            f"{self.base_url}/detect/{module}", json={"text": text, "metadata": meta}
        )
        r.raise_for_status()
        return r.json()

    async def _anonymize(self, text: str) -> dict:
        r = await self._http.post(f"{self.base_url}/anonymize", json={"text": text})
        r.raise_for_status()
        return r.json()  # {"id": ..., "text": ...}

    async def _deanonymize(self, mapping_id: str, text: str) -> str:
        r = await self._http.post(
            f"{self.base_url}/deanonymize", json={"id": mapping_id, "text": text}
        )
        if r.status_code == 404:  # маппинг истёк (TTL) — оставляем как есть
            return text
        r.raise_for_status()
        return r.json()["text"]

    # ------------------------------------------------------------------ #
    # Вспомогательное
    # ------------------------------------------------------------------ #
    @staticmethod
    def _meta(data: dict, stage: str, user: UserAPIKeyAuth | None) -> dict:
        """Метаданные прогона -> в логи гуарда (фильтруются в админке)."""
        m = {"source": "litellm", "stage": stage}
        if data.get("model"):
            m["model"] = str(data["model"])
        uid = getattr(user, "user_id", None) if user else None
        if uid:
            m["user_id"] = str(uid)
        alias = getattr(user, "key_alias", None) if user else None
        if alias:
            m["key_alias"] = str(alias)
        return m

    @staticmethod
    def _last_user_text(messages: list) -> str:
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                return m["content"]
        return ""

    def _guard_unreachable(self, where: str, err: Exception):
        """Гуард недоступен: fail-closed -> 503, иначе пропускаем (warning)."""
        if self.fail_closed:
            raise HTTPException(503, f"guardrails service unreachable ({where})")
        _log.warning("lite-guardrails: %s недоступен (%s) — пропускаю", where, err)

    # ------------------------------------------------------------------ #
    # PRE-CALL: проверка входящего промпта
    # ------------------------------------------------------------------ #
    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: str,
    ):
        if not self.check_input:
            return data
        messages = data.get("messages")
        if not messages:
            return data

        meta = self._meta(data, "input", user_api_key_dict)
        user_text = self._last_user_text(messages)

        try:
            # --- relevant: нерелевантный/мусорный запрос -------------------
            if self.relevant_action != "off" and user_text:
                res = await self._detect("relevant", user_text, meta)
                if not res.get("RELEVANT", True):
                    if self.relevant_action == "block":
                        raise HTTPException(
                            400, f"запрос отклонён: нерелевантно (категория: {res.get('category')})"
                        )

            # --- nsfw: непристойный ввод ----------------------------------
            if self.nsfw_action != "off" and user_text:
                res = await self._detect("nsfw", user_text, meta)
                if res.get("NSFW_DETECT") and self.nsfw_action == "block":
                    raise HTTPException(400, "запрос отклонён: NSFW во вводе")

            # --- pii ------------------------------------------------------
            if self.pii_action == "block" and user_text:
                res = await self._detect("pii", user_text, meta)
                if res.get("PII_DETECT"):
                    raise HTTPException(400, "запрос отклонён: обнаружены PII")
            elif self.pii_action == "log" and user_text:
                await self._detect("pii", user_text, meta)
            elif self.pii_action == "anonymize":
                await self._anonymize_messages(messages, data)

        except HTTPException:
            raise  # это наш блок — пробрасываем
        except httpx.HTTPError as e:
            self._guard_unreachable("pre-call", e)

        return data

    async def _anonymize_messages(self, messages: list, data: dict):
        """Анонимизирует строковые сообщения одним вызовом /anonymize (сквозные
        теги) и сохраняет id маппинга для деанонимизации ответа."""
        idxs = [
            i for i, m in enumerate(messages) if isinstance(m.get("content"), str) and m["content"]
        ]
        if not idxs:
            return
        joined = _SEP.join(messages[i]["content"] for i in idxs)
        res = await self._anonymize(joined)
        if res["text"] == joined:
            return  # PII не найдено — менять нечего
        parts = res["text"].split(_SEP)
        if len(parts) != len(idxs):
            # разделитель не уцелел (крайне маловероятно) — не рискуем содержимым
            _log.warning("lite-guardrails: маркер сегментации повреждён, пропускаю анонимизацию")
            return
        for i, part in zip(idxs, parts):
            messages[i]["content"] = part
        data.setdefault("metadata", {})[_META_PII_ID] = res["id"]

    # ------------------------------------------------------------------ #
    # POST-CALL: обработка ответа модели
    # ------------------------------------------------------------------ #
    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        if not self.check_output:
            return response

        meta = self._meta(data, "output", user_api_key_dict)
        pii_id = (data.get("metadata") or {}).get(_META_PII_ID)
        pairs = self._choice_contents(response)

        try:
            # --- деанонимизация: возвращаем реальные значения вместо тегов --
            if pii_id and self.pii_action == "anonymize":
                for msg, content in pairs:
                    if isinstance(content, str) and content:
                        restored = await self._deanonymize(pii_id, content)
                        self._set_content(msg, restored)

            # --- nsfw в ответе модели -------------------------------------
            if self.nsfw_action != "off":
                for msg, content in self._choice_contents(response):
                    if isinstance(content, str) and content:
                        res = await self._detect("nsfw", content, meta)
                        if res.get("NSFW_DETECT") and self.nsfw_action == "block":
                            raise HTTPException(400, "ответ заблокирован: NSFW")

        except HTTPException:
            raise
        except httpx.HTTPError as e:
            self._guard_unreachable("post-call", e)

        return response

    # --- доступ к содержимому ответа (объект ModelResponse или dict) ------
    @staticmethod
    def _choice_contents(response):
        out = []
        choices = getattr(response, "choices", None)
        if not choices and isinstance(response, dict):
            choices = response.get("choices")
        for ch in choices or []:
            msg = getattr(ch, "message", None)
            if msg is None and isinstance(ch, dict):
                msg = ch.get("message")
            if msg is None:
                continue
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            out.append((msg, content))
        return out

    @staticmethod
    def _set_content(msg, value: str):
        if isinstance(msg, dict):
            msg["content"] = value
        else:
            msg.content = value
