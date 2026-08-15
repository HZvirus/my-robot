from uuid import uuid4

from app.core.logger import get_logger
from app.services.llm_client import OpenAICompatClient, llm_client

logger = get_logger(__name__)


class AIService:
    def __init__(self, client: OpenAICompatClient | None = None) -> None:
        self._client = client or llm_client

    async def chat(self, message: str, conversation_id: str | None = None) -> tuple[str, str]:
        conv_id = conversation_id or str(uuid4())
        logger.info("chat request conv=%s msg=%s", conv_id, message)

        parts: list[str] = []
        async for token in self._client.chat_stream(
            [{"role": "user", "content": message}]
        ):
            parts.append(token)
        return "".join(parts), conv_id


ai_service = AIService()
