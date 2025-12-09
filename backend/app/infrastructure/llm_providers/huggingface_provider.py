import httpx
from .base import BaseLLMProvider


class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace Inference API provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://router.huggingface.co/hf-inference/models"

    @property
    def provider_id(self) -> str:
        return "huggingface"

    @property
    def name(self) -> str:
        return "HuggingFace"

    @property
    def available_models(self) -> list[str]:
        # Using models that don't require gated access approval
        return [
            "HuggingFaceH4/zephyr-7b-beta",
            "tiiuae/falcon-7b-instruct",
            "bigscience/bloom-560m",
            "google/flan-t5-base",
            "EleutherAI/gpt-neo-1.3B",
        ]

    async def is_available(self) -> bool:
        if not self.api_key:
            print(f"HuggingFace: No API key configured")
            return False
        try:
            async with httpx.AsyncClient() as client:
                # Test with a simple POST request to a small model
                response = await client.post(
                    f"{self.base_url}/gpt2",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"inputs": "test"},
                    timeout=10.0,
                )
                print(f"HuggingFace availability check: status={response.status_code}")
                # 200 = success, 503 = model loading (still available)
                return response.status_code in [200, 503]
        except Exception as e:
            print(f"HuggingFace availability check failed: {e}")
            return False

    async def _call_api(self, prompt: str, model: str) -> tuple[str, int, int]:
        async with httpx.AsyncClient() as client:
            # Format prompt for instruction-tuned models
            formatted_prompt = f"<|user|>\n{prompt}\n<|assistant|>\n"

            response = await client.post(
                f"{self.base_url}/{model}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": formatted_prompt,
                    "parameters": {
                        "max_new_tokens": 1024,
                        "temperature": 0.7,
                        "return_full_text": False,
                    },
                },
                timeout=120.0,  # HF can be slow for cold starts
            )
            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            if isinstance(data, list) and len(data) > 0:
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                content = data.get("generated_text", "")
            else:
                content = str(data)

            # Estimate tokens (HF doesn't always return usage)
            input_tokens = len(prompt.split()) * 1.3  # rough estimate
            output_tokens = len(content.split()) * 1.3

            return content, int(input_tokens), int(output_tokens)
