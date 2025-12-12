import httpx
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """Gemini Inference Providers API (OpenAI-compatible)"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Gemini OpenAI-compatible endpoint
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def available_models(self) -> list[str]:
        return [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            # OpenAI-compatible payload format
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0,
                )

                response.raise_for_status()
                data = response.json()

                # OpenAI-compatible response format
                content = data["choices"][0]["message"]["content"]

                # Get token usage if available
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", int(len(prompt.split()) * 1.3))
                output_tokens = usage.get("completion_tokens", int(len(content.split()) * 1.3))

                return content.strip(), input_tokens, output_tokens

            except httpx.HTTPStatusError as e:
                error_detail = ""
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("error", {}).get("message", e.response.text)
                except:
                    error_detail = e.response.text

                if e.response.status_code == 401:
                    raise Exception("Invalid Gemini API Key")
                if e.response.status_code == 404:
                    raise Exception(f"Model {model} not found or not available")
                if e.response.status_code == 422:
                    raise Exception(f"Model {model} validation error: {error_detail}")
                raise Exception(f"Gemini API error: {e.response.status_code} - {error_detail}")