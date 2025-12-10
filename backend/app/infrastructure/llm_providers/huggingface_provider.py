import httpx
import asyncio
from .base import BaseLLMProvider

class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace Inference API provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Use the standard inference URL
        self.base_url = "https://api-inference.huggingface.co/models"

    @property
    def provider_id(self) -> str:
        return "huggingface"

    @property
    def name(self) -> str:
        return "HuggingFace"

    @property
    def available_models(self) -> list[str]:
        return [
            # High-Performance Chat Models (Recommended)
            "mistralai/Mistral-7B-Instruct-v0.3",
            "HuggingFaceH4/zephyr-7b-beta",
            "microsoft/Phi-3-mini-4k-instruct",
            
            # DeepSeek (Check availability - usually requires Pro or might be busy)
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
            
            # Llama 3 (Requires accepting license on HF website first!)
            "meta-llama/Llama-3.1-8B-Instruct",
        ]

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        if self.api_key.startswith("hf_"):
            return True
        return False

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
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
                # CRITICAL FIX: Tells HF to wait for the model to load (Cold Start)
                # instead of returning a 503 error immediately.
                "x-wait-for-model": "true" 
            }

            # Use the model-specific chat endpoint for better routing reliability
            url = f"{self.base_url}/{model}/v1/chat/completions"
            
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=120.0,  # Increased timeout for loading
                )
                
                # Handle Loading State Explicitly if header fails
                if response.status_code == 503:
                    error_data = response.json()
                    estimated_time = error_data.get("estimated_time", 20.0)
                    print(f"Model {model} is cold. Loading... ({estimated_time}s)")
                    await asyncio.sleep(estimated_time)
                    # Retry once
                    response = await client.post(
                        url, headers=headers, json=payload, timeout=120.0
                    )

                response.raise_for_status()
                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                else:
                    raise Exception(f"Unexpected response format: {data}")

                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", len(prompt.split()) * 1.3)
                output_tokens = usage.get("completion_tokens", len(content.split()) * 1.3)

                return content.strip(), int(input_tokens), int(output_tokens)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise Exception("Invalid API Key or Gated Model Access (Accept License on HF)")
                raise e