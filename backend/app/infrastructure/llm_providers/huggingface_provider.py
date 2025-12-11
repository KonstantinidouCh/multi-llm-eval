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
            "Qwen/Qwen2.5-7B-Instruct-1M",               # Long context (1M tokens)
            "meta-llama/Llama-3.3-70B-Instruct",         # Latest Llama 3.3
            "mistralai/Mixtral-8x7B-Instruct-v0.1",      # Mixtral MoE
            "microsoft/Phi-3-mini-4k-instruct",          # Small but capable
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
                    error_detail = error_data.get("error", {}).get("message", e.response.text)
                except:
                    error_detail = e.response.text

                if e.response.status_code == 401:
                    raise Exception("Invalid HuggingFace API Key")
                if e.response.status_code == 404:
                    raise Exception(f"Model {model} not found or not available")
                if e.response.status_code == 422:
                    raise Exception(f"Model {model} validation error: {error_detail}")
                raise Exception(f"HuggingFace API error: {e.response.status_code} - {error_detail}")