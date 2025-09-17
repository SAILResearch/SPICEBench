"""
This module deals with connecting the issue_labelr to various LLMs. 
The OpenAIProvider, ClaudeProvider, and LocalProvider are all redundant with the `litellm`, 
but keeping them for now for backwards compatibility.


"""

import json
import httpx
from anthropic import AsyncAnthropic
from pathlib import Path
from abc import ABC, abstractmethod
import os
from litellm import acompletion, completion_cost
import logging
import time

# -------------------------------
# Shared Model Configuration Loader
# -------------------------------


class ModelConfigLoader:
    _config = None

    @classmethod
    def load_config(cls):
        if cls._config is None:
            config_path = Path(__file__).parent / "model_parameters.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = json.load(f)
        return cls._config

    @classmethod
    def get_model_config(cls, model_name):
        config = cls.load_config()
        if model_name not in config:
            raise ValueError(
                f"Model '{model_name}' not found in model_parameters.json. "
                f"Available models: {list(config.keys())}"
            )
        return config[model_name]

# -------------------------------
# Base Provider Interface
# -------------------------------


class BaseModelProvider(ABC):
    @abstractmethod
    async def request(self, prompt: str, model: str) -> dict:
        pass

# -------------------------------
# OpenAI Provider
# -------------------------------



class OpenAIProvider(BaseModelProvider):
    def __init__(self):
        super().__init__()
        self.API_KEY = os.environ.get("OPENAI_API_KEY")

    async def request(self, prompt: str, model: str) -> dict:
        config = ModelConfigLoader.get_model_config(model)
        try:
            async with httpx.AsyncClient(timeout=config.get("timeout", 30.0)) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": config.get("temperature", 0.7),
                        "max_tokens": config.get("max_tokens", 500)
                    },
                    headers={"Authorization": f"Bearer {self.API_KEY}"}
                )
                raw_content = response.json(
                )["choices"][0]["message"]["content"]
                return raw_content
        except Exception as e:
            raise RuntimeError(
                f"[OpenAIProvider] Error during model call for '{model}': {e}")

# -------------------------------
# Claude Provider
# -------------------------------



class ClaudeProvider(BaseModelProvider):
    def __init__(self):
        CLAUDE_API_KEY = None
        self.client = AsyncAnthropic(api_key=CLAUDE_API_KEY)

    async def request(self, prompt: str, model: str) -> dict:
        config = ModelConfigLoader.get_model_config(model)
        try:
            response = await self.client.messages.create(
                max_tokens=config.get("max_tokens", 512),
                messages=[{"role": "user", "content": prompt}],
                model=model
            )
            raw_content = response.content[0].text
            return raw_content
        except Exception as e:
            raise RuntimeError(
                f"[ClaudeProvider] Error during model call for '{model}': {e}")

# -------------------------------
# Local Provider
# -------------------------------


class ProxyHelper():

    @staticmethod
    def bypass_proxy(ip: str) -> None:
        """Add an IP to the no_proxy environment variable"""
        current = os.environ.get('no_proxy', '')
        if current:
            # Add to existing no_proxy if it's not already there
            if ip not in current.split(','):
                os.environ['no_proxy'] = f"{current},{ip}"
        else:
            # Create no_proxy if it doesn't exist
            os.environ['no_proxy'] = ip

        # Also set the uppercase version as some applications use that
        os.environ['NO_PROXY'] = os.environ['no_proxy']


class LocalProvider(BaseModelProvider):

    def __init__(self):
        super().__init__()
        self.host_ip = os.environ.get("LOCAL_MODEL_HOST", "localhost")
        ProxyHelper.bypass_proxy(self.host_ip)

    async def request(self, prompt: str, model: str) -> dict:
        config = ModelConfigLoader.get_model_config(model)
        try:
            async with httpx.AsyncClient(timeout=config.get("timeout", 120.0)) as client:
                response = await client.post(
                    f"http://{self.host_ip}:11434/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": config.get("max_tokens", 1000)
                    },
                    headers={"Authorization": "Bearer ollama"}
                )
                # TODO: Add proper error handling for API response validation
                raw_content = response.json(
                )["choices"][0]["message"]["content"]

                return raw_content
        except Exception as e:
            raise RuntimeError(
                f"[LocalProvider] Error during model call for '{model}': {e}")


class LiteLLMProvider:
    """Async wrapper for LiteLLM (OpenAI‐style)."""

    async def request(self, prompt: str, model: str):
        start = time.perf_counter()

        call_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = await acompletion(**call_kwargs)
        
        end = time.perf_counter()
        latency = end - start  # seconds

        logger = logging.getLogger("litellm")
        # pull out usage & cost
        usage = resp.get("usage", {})
        in_toks = usage.get("prompt_tokens")
        out_toks = usage.get("completion_tokens")
        cost_usd = resp._hidden_params.get("response_cost")\


        # log full JSON + cost in one shot
        logger.info(
            f"MODEL={model} TOKENS_IN={in_toks} TOKENS_OUT={out_toks} COST={cost_usd} LATENCY={latency:.2f}s")

        return resp["choices"][0]["message"]["content"]

# -------------------------------
# Director
# -------------------------------


class ModelProviderDirector:
    _registry = {
        "openai": OpenAIProvider(),
        "claude": ClaudeProvider(),
        "local": LocalProvider(),
        "litellm": LiteLLMProvider()
    }

    @classmethod
    def get_provider(cls, name: str):
        if name not in cls._registry:
            raise ValueError(
                f"Unknown model provider '{name}'. Available: {list(cls._registry.keys())}")
        return cls._registry[name]
