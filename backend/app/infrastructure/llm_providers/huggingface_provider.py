import httpx
import asyncio
from .base import BaseLLMProvider

class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace Inference API provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # UPDATED: Standard inference URL
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
            "HuggingFaceH4/zephyr-7b-beta",
            "tiiuae/falcon-7b-instruct",
            "bigscience/bloom-560m",
            "google/flan-t5-base",
            "EleutherAI/gpt-neo-1.3B",
        ]

    async def is_available(self) -> bool:
        if not self.api_key:
            print("HuggingFace: No API key configured")
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/gpt2",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"inputs": "test"},
                    timeout=10.0,
                )
                # 503 is acceptable here as it means authentication worked
                return response.status_code in [200, 503]
        except Exception as e:
            print(f"HuggingFace availability check failed: {e}")
            return False

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            
            # REMOVED: Hardcoded <|user|> template. 
            # This template is specific to Zephyr and breaks other models (like T5).
            # Sending raw prompt is safer for a generic list of models.
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    # Note: return_full_text is sometimes ignored by older models,
                    # so we may need to strip the prompt manually in post-processing.
                    "return_full_text": False, 
                },
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # CRITICAL FIX: Forces API to wait for model loading instead of returning 503
                "x-wait-for-model": "true", 
                "x-use-cache": "false" 
            }

            response = await client.post(
                f"{self.base_url}/{model}",
                headers=headers,
                json=payload,
                # Increased timeout to account for model loading time
                timeout=120.0, 
            )

            response.raise_for_status()
            data = response.json()

            # Handle response extraction
            content = ""
            if isinstance(data, list) and len(data) > 0:
                # Standard text-generation format: [{'generated_text': '...'}]
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                # Some models (like T5) might return differently or return errors as dicts
                content = data.get("generated_text", str(data))
            else:
                content = str(data)

            # Manual cleanup: If the model ignored 'return_full_text': False, 
            # we strip the prompt from the start to avoid duplication.
            if content.startswith(prompt):
                content = content[len(prompt):]

            # Estimate tokens
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(content.split()) * 1.3

            return content.strip(), int(input_tokens), int(output_tokens)