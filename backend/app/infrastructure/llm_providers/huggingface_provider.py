import httpx
from .base import BaseLLMProvider

class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace Inference Providers API (OpenAI-compatible)"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # New HuggingFace router endpoint (OpenAI-compatible)
        self.base_url = "https://router.huggingface.co/v1/chat/completions"

    @property
    def provider_id(self) -> str:
        return "huggingface"

    @property
    def name(self) -> str:
        return "HuggingFace"

    @property
    def available_models(self) -> list[str]:
        return [
            # Recommended models from HuggingFace Inference Providers
            "google/gemma-2-2b-it",
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
            # DeepSeek reasoning model
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
             # Additional recommended models
            "deepseek-ai/DeepSeek-R1",                    # Full DeepSeek reasoning model
            "Qwen/Qwen2.5-72B-Instruct",                  # Larger Qwen model
            "google/gemma-2-9b-it",  
        ]

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        if self.api_key.startswith("hf_"):
            return True
        return False

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            # OpenAI-compatible payload format
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7,
                "stream": False
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            try:
                response = await client.post(
                    self.base_url,
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
                    error_obj = error_data.get("error", {})
                    if isinstance(error_obj, dict):
                        error_detail = error_obj.get("message", e.response.text)
                    else:
                        error_detail = str(error_obj) or e.response.text
                except Exception:
                    error_detail = e.response.text[:500] if e.response.text else str(e.response.status_code)

                if e.response.status_code == 401:
                    raise Exception(f"Invalid HuggingFace API Key: {error_detail}")
                if e.response.status_code == 404:
                    raise Exception(f"Model {model} not found or not available: {error_detail}")
                if e.response.status_code == 422:
                    raise Exception(f"Model {model} validation error: {error_detail}")
                if e.response.status_code == 429:
                    raise Exception(f"HuggingFace rate limit exceeded: {error_detail}")
                if e.response.status_code == 503:
                    raise Exception(f"HuggingFace service unavailable (model may be loading): {error_detail}")
                raise Exception(f"HuggingFace API error {e.response.status_code}: {error_detail}")

            except httpx.ConnectError as e:
                raise Exception(f"Failed to connect to HuggingFace API: {str(e)}")
            except httpx.TimeoutException:
                raise Exception(f"HuggingFace API request timed out after 120 seconds")