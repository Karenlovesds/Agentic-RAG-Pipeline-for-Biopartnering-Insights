"""LLM and Embeddings provider adapter for OpenAI and Ollama."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import os

import requests
from loguru import logger

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency load guard
    OpenAI = None  # type: ignore


@dataclass
class LLMResponse:
    content: str
    raw: Dict[str, Any]


class BaseLLMProvider:
    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError

    def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        raise NotImplementedError


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: str = "gpt-4o-mini", default_embedding_model: str = "text-embedding-3-small"):
        if OpenAI is None:
            raise RuntimeError("openai package not available")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"), base_url=base_url)
        self.default_model = default_model
        self.default_embedding_model = default_embedding_model

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.0) -> LLMResponse:
        mdl = model or self.default_model
        logger.debug(f"OpenAI chat using model={mdl}")
        resp = self.client.chat.completions.create(model=mdl, messages=messages, temperature=temperature)
        content = resp.choices[0].message.content or ""
        return LLMResponse(content=content, raw=resp.model_dump() if hasattr(resp, "model_dump") else dict(resp))

    def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        mdl = model or self.default_embedding_model
        logger.debug(f"OpenAI embed using model={mdl} for n={len(texts)}")
        resp = self.client.embeddings.create(model=mdl, input=texts)
        return [d.embedding for d in resp.data]


class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str = "http://localhost:11434", default_model: str = "llama3.1", default_embedding_model: str = "nomic-embed-text"):
        # Use OpenAI-compatible API if available; otherwise fall back to native endpoints
        self.base_url = host.rstrip("/")
        self.oai_url = f"{self.base_url}/v1"
        self.default_model = default_model
        self.default_embedding_model = default_embedding_model

    def _oai_chat(self, messages: List[Dict[str, str]], model: str, temperature: float) -> Optional[LLMResponse]:
        try:
            url = f"{self.oai_url}/chat/completions"
            headers = {"Authorization": "Bearer ollama"}
            payload = {"model": model, "messages": messages, "temperature": temperature}
            r = requests.post(url, headers=headers, json=payload, timeout=300)
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                return LLMResponse(content=content, raw=data)
            return None
        except Exception as e:
            logger.warning(f"Ollama OpenAI-compatible chat failed: {e}")
            return None

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None, temperature: float = 0.0) -> LLMResponse:
        mdl = model or self.default_model
        # Try OpenAI-compatible first
        resp = self._oai_chat(messages, mdl, temperature)
        if resp is not None:
            return resp
        # Fallback to native generate endpoint (single-turn)
        try:
            url = f"{self.base_url}/api/generate"
            prompt = "\n\n".join([m["content"] for m in messages if m["role"] in {"system", "user"}])
            payload = {"model": mdl, "prompt": prompt, "stream": False, "options": {"temperature": temperature}}
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            return LLMResponse(content=data.get("response", ""), raw=data)
        except Exception as e:
            raise RuntimeError(f"Ollama chat failed: {e}")

    def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        mdl = model or self.default_embedding_model
        # Try OpenAI-compatible embeddings
        try:
            url = f"{self.oai_url}/embeddings"
            headers = {"Authorization": "Bearer ollama"}
            payload = {"model": mdl, "input": texts}
            r = requests.post(url, headers=headers, json=payload, timeout=300)
            if r.status_code == 200:
                data = r.json()
                return [d["embedding"] for d in data["data"]]
        except Exception as e:
            logger.warning(f"Ollama OpenAI-compatible embeddings failed: {e}")
        # Fallback to native embeddings endpoint (single input at a time)
        vectors: List[List[float]] = []
        for t in texts:
            url = f"{self.base_url}/api/embeddings"
            payload = {"model": mdl, "prompt": t}
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            vectors.append(data.get("embedding", []))
        return vectors


def build_provider(provider: str, chat_model: Optional[str] = None, embedding_model: Optional[str] = None, openai_api_key: Optional[str] = None) -> BaseLLMProvider:
    p = provider.lower().strip()
    if p == "openai":
        return OpenAIProvider(api_key=openai_api_key, default_model=chat_model or "gpt-4o-mini", default_embedding_model=embedding_model or "text-embedding-3-small")
    if p == "ollama":
        return OllamaProvider(default_model=chat_model or "llama3.1", default_embedding_model=embedding_model or "nomic-embed-text")
    raise ValueError(f"Unknown provider: {provider}")


