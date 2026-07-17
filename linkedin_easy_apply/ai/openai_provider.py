"""OpenAI-backed advisory provider (optional dependency)."""

from __future__ import annotations

import json
import os

from loguru import logger

from linkedin_easy_apply.ai.models import AIResult, TailoringSuggestion
from linkedin_easy_apply.ai.provider import AIProvider
from linkedin_easy_apply.config.models import AIConfig

_SYSTEM_PROMPT = (
    "You are a career assistant. Given a job posting and optionally a resume, "
    "assess the candidate fit. Respond ONLY with a compact JSON object using the "
    "keys: match_percent (0-100 number), missing_skills (list of strings), "
    "recommendation (short string), reasons (list of strings), should_apply "
    "(boolean). Do not include any prose outside the JSON."
)

_TAILOR_SYSTEM_PROMPT = (
    "You help re-emphasise an EXISTING resume for a specific job. You must NOT "
    "invent experience. You are given the job and the candidate's resume skill "
    "categories. Choose the best short headline (drawn from the candidate's real "
    "profile) and reorder the given categories from most to least relevant to the "
    "job. Respond ONLY with a compact JSON object with keys: title (short string), "
    "skills_order (list containing ONLY names from the provided categories, most "
    "relevant first), reason (short string). Do not add categories that were not "
    "provided. Do not include any prose outside the JSON."
)


class OpenAIProvider(AIProvider):
    """Use the OpenAI Chat Completions API to advise on a job."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "openai package not installed. Install with 'pip install .[ai]'."
            ) from exc
        api_key = os.environ.get(self._config.api_key_env)
        if not api_key:
            raise RuntimeError(f"Environment variable '{self._config.api_key_env}' is not set.")
        self._client = OpenAI(api_key=api_key)
        return self._client

    def evaluate_job(
        self,
        *,
        job_title: str,
        job_description: str,
        resume_text: str | None = None,
    ) -> AIResult:
        user_prompt = (
            f"JOB TITLE:\n{job_title}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:6000]}\n\n"
            f"RESUME:\n{(resume_text or 'Not provided')[:6000]}"
        )
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or "{}"
            return self._parse(content)
        except Exception as exc:  # pragma: no cover - network/optional
            logger.warning("AI evaluation failed: {}", exc)
            return AIResult(recommendation=f"AI error: {exc}", should_apply=None)

    def suggest_tailoring(
        self,
        *,
        job_title: str,
        job_description: str,
        available_categories: list[str],
        master_title: str | None = None,
    ) -> TailoringSuggestion | None:
        if not available_categories:
            return None
        user_prompt = (
            f"JOB TITLE:\n{job_title}\n\n"
            f"JOB DESCRIPTION:\n{(job_description or '')[:6000]}\n\n"
            f"CANDIDATE HEADLINE (current):\n{master_title or 'Not provided'}\n\n"
            f"AVAILABLE SKILL CATEGORIES (choose/reorder ONLY from these):\n"
            f"{', '.join(available_categories)}"
        )
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                messages=[
                    {"role": "system", "content": _TAILOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or "{}"
            return self._parse_tailoring(content, available_categories)
        except Exception as exc:  # pragma: no cover - network/optional
            logger.warning("AI tailoring failed: {}", exc)
            return None

    @staticmethod
    def _parse_tailoring(
        content: str, available_categories: list[str]
    ) -> TailoringSuggestion | None:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if "\n" in text else text
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        # Constrain to real categories only - never trust the model to add content.
        allowed = {c.lower(): c for c in available_categories}
        order = [
            allowed[str(c).lower()]
            for c in (data.get("skills_order") or [])
            if str(c).lower() in allowed
        ]
        title = data.get("title")
        if not title and not order:
            return None
        return TailoringSuggestion(
            title=(str(title).strip() or None) if title else None,
            skills_order=order,
            cluster="ai",
            reason=str(data.get("reason") or "AI re-emphasis"),
        )

    @staticmethod
    def _parse(content: str) -> AIResult:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if "\n" in text else text
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return AIResult(recommendation=content[:200], should_apply=None, raw=content)
        return AIResult(
            match_percent=_as_float(data.get("match_percent")),
            missing_skills=list(data.get("missing_skills") or []),
            recommendation=data.get("recommendation"),
            reasons=list(data.get("reasons") or []),
            should_apply=data.get("should_apply"),
            raw=data,
        )


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
