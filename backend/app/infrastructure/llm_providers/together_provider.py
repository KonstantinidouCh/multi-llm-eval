import httpx
from .base import BaseLLMProvider


class TogetherProvider(BaseLLMProvider):
    """Together AI provider with free tier"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.together.xyz/v1"

    @property
    def provider_id(self) -> str:
        return "together"

    @property
    def name(self) -> str:
        return "Together AI"

    @property
    def available_models(self) -> list[str]:
        return [
            "meta-llama/Llama-3-70b-chat-hf",
            "meta-llama/Llama-3-8b-chat-hf",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "mistralai/Mistral-7B-Instruct-v0.2",
            "togethercomputer/RedPajama-INCITE-7B-Chat",
            "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",
        ]

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return content, input_tokens, output_tokens

    def _get_cost_per_token(self, model: str) -> tuple[float, float]:
        # Together AI pricing (approximate, free tier has limits)
        costs = {
            "meta-llama/Llama-3-70b-chat-hf": (0.0000009, 0.0000009),
            "meta-llama/Llama-3-8b-chat-hf": (0.0000002, 0.0000002),
            "mistralai/Mixtral-8x7B-Instruct-v0.1": (0.0000006, 0.0000006),
        }
        return costs.get(model, (0.0, 0.0))
