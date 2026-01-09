import httpx
from .base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    """Groq API provider with free tier"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"

    @property
    def provider_id(self) -> str:
        return "groq"

    @property
    def name(self) -> str:
        return "Groq"

    @property
    def available_models(self) -> list[str]:
        return [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
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
            try:
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

            except httpx.HTTPStatusError as e:
                error_detail = ""
                try:
                    error_data = e.response.json()
                    # Groq returns error in {"error": {"message": "...", "type": "...", "code": "..."}}
                    error_obj = error_data.get("error", {})
                    if isinstance(error_obj, dict):
                        error_detail = error_obj.get("message", e.response.text)
                        error_type = error_obj.get("type", "")
                        error_code = error_obj.get("code", "")
                        if error_type or error_code:
                            error_detail = f"{error_detail} (type: {error_type}, code: {error_code})"
                    else:
                        error_detail = str(error_obj) or e.response.text
                except Exception:
                    error_detail = e.response.text[:500] if e.response.text else str(e.response.status_code)

                if e.response.status_code == 401:
                    raise Exception(f"Invalid Groq API Key: {error_detail}")
                if e.response.status_code == 404:
                    raise Exception(f"Model {model} not found: {error_detail}")
                if e.response.status_code == 429:
                    raise Exception(f"Groq rate limit exceeded: {error_detail}")
                if e.response.status_code == 503:
                    raise Exception(f"Groq service unavailable: {error_detail}")
                raise Exception(f"Groq API error {e.response.status_code}: {error_detail}")

            except httpx.ConnectError as e:
                raise Exception(f"Failed to connect to Groq API: {str(e)}")
            except httpx.TimeoutException:
                raise Exception(f"Groq API request timed out after 60 seconds")
