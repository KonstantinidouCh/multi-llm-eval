import httpx
from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama local provider - completely free"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    @property
    def available_models(self) -> list[str]:
        return [
            "llama3",
            "llama3:8b",
            "llama3:70b",
            "mistral",
            "mistral:7b",
            "codellama",
            "phi3",
            "gemma:7b",
            "qwen2:7b",
        ]

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False

    async def get_installed_models(self) -> list[str]:
        """Get list of models actually installed in Ollama"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024,
                    },
                },
                timeout=120.0,  # Local models can be slow
            )
            response.raise_for_status()
            data = response.json()

            content = data.get("response", "")
            # Ollama provides token counts
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)

            return content, input_tokens, output_tokens

    def _get_cost_per_token(self, model: str) -> tuple[float, float]:
        # Ollama is local and free
        return (0.0, 0.0)
