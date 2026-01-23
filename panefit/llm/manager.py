"""
LLM Manager - handles multiple LLM providers.
"""

import os
import json
import subprocess
from typing import Optional
import urllib.request
import urllib.error

from .base import LLMProvider, LLMAnalysisResult


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    @property
    def name(self) -> str:
        return "openai"

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("openai package not installed")
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_content(self, content: str, context: Optional[str] = None) -> LLMAnalysisResult:
        system = """Analyze terminal content. Return JSON:
{"importance_score": 0-1, "interestingness_score": 0-1, "summary": "...", "topics": [...], "predicted_activity": "high/medium/low"}"""

        user = f"Content:\n{content[:3000]}"
        if context:
            user += f"\nContext: {context}"

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.3,
                max_tokens=500
            )
            text = response.choices[0].message.content
            data = json.loads(text)
            return LLMAnalysisResult(
                importance_score=float(data.get("importance_score", 0.5)),
                interestingness_score=float(data.get("interestingness_score", 0.5)),
                summary=data.get("summary", ""),
                topics=data.get("topics", []),
                predicted_activity=data.get("predicted_activity", "medium"),
                raw_response=text
            )
        except Exception as e:
            return LLMAnalysisResult(raw_response=str(e))


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    @property
    def name(self) -> str:
        return "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed")
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_content(self, content: str, context: Optional[str] = None) -> LLMAnalysisResult:
        system = """Return JSON only: {"importance_score": 0-1, "interestingness_score": 0-1, "summary": "...", "topics": [...], "predicted_activity": "high/medium/low"}"""

        user = f"Analyze:\n{content[:3000]}"
        if context:
            user += f"\nContext: {context}"

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            text = response.content[0].text
            data = json.loads(text)
            return LLMAnalysisResult(
                importance_score=float(data.get("importance_score", 0.5)),
                interestingness_score=float(data.get("interestingness_score", 0.5)),
                summary=data.get("summary", ""),
                topics=data.get("topics", []),
                predicted_activity=data.get("predicted_activity", "medium"),
                raw_response=text
            )
        except Exception as e:
            return LLMAnalysisResult(raw_response=str(e))


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    @property
    def name(self) -> str:
        return "ollama"

    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["curl", "-s", f"{self.host}/api/tags"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def analyze_content(self, content: str, context: Optional[str] = None) -> LLMAnalysisResult:
        prompt = f"""Analyze terminal content. Return ONLY JSON:
{{"importance_score": <0-1>, "interestingness_score": <0-1>, "summary": "<brief>", "topics": ["..."], "predicted_activity": "<high/medium/low>"}}

Content:
{content[:2000]}

JSON:"""

        try:
            data = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            }).encode()

            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                text = result.get("response", "")

                # Extract JSON
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    return LLMAnalysisResult(
                        importance_score=float(parsed.get("importance_score", 0.5)),
                        interestingness_score=float(parsed.get("interestingness_score", 0.5)),
                        summary=parsed.get("summary", ""),
                        topics=parsed.get("topics", []),
                        predicted_activity=parsed.get("predicted_activity", "medium"),
                        raw_response=text
                    )
        except Exception as e:
            return LLMAnalysisResult(raw_response=str(e))

        return LLMAnalysisResult()


class LLMManager:
    """Manages multiple LLM providers."""

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        ollama_model: Optional[str] = None,
        preferred_provider: Optional[str] = None
    ):
        self.providers: dict[str, LLMProvider] = {}

        if openai_key or os.environ.get("OPENAI_API_KEY"):
            self.providers["openai"] = OpenAIProvider(api_key=openai_key)

        if anthropic_key or os.environ.get("ANTHROPIC_API_KEY"):
            self.providers["anthropic"] = AnthropicProvider(api_key=anthropic_key)

        if ollama_model:
            self.providers["ollama"] = OllamaProvider(model=ollama_model)
        else:
            ollama = OllamaProvider()
            if ollama.is_available():
                self.providers["ollama"] = ollama

        self.preferred_provider = preferred_provider

    def get_provider(self) -> Optional[LLMProvider]:
        """Get best available provider."""
        if self.preferred_provider and self.preferred_provider in self.providers:
            provider = self.providers[self.preferred_provider]
            if provider.is_available():
                return provider

        for name in ["anthropic", "openai", "ollama"]:
            if name in self.providers:
                provider = self.providers[name]
                if provider.is_available():
                    return provider

        return None

    def is_available(self) -> bool:
        """Check if any provider is available."""
        return self.get_provider() is not None

    def analyze_content(self, content: str, context: Optional[str] = None) -> Optional[LLMAnalysisResult]:
        """Analyze using best available provider."""
        provider = self.get_provider()
        return provider.analyze_content(content, context) if provider else None

    def analyze_relationships(self, panes: list[tuple[str, str]]) -> dict[tuple[str, str], float]:
        """Analyze pane relationships."""
        provider = self.get_provider()
        return provider.analyze_relationships(panes) if provider else {}
