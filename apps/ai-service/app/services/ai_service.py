from uuid import uuid4

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class AIService:
    def __init__(self) -> None:
        self.api_key = settings.AI_API_KEY
        self.api_base = settings.AI_API_BASE
        self.model = settings.AI_MODEL

    async def chat(self, message: str, conversation_id: str | None = None) -> tuple[str, str]:
        conv_id = conversation_id or str(uuid4())
        logger.info("chat request conv=%s msg=%s", conv_id, message)

        if not self.api_key:
            return "AI service is not configured.", conv_id

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            return reply, conv_id


ai_service = AIService()
