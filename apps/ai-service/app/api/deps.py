from fastapi import Depends, Header


def get_conversation_id(x_conversation_id: str | None = Header(default=None)) -> str | None:
    return x_conversation_id


ConversationIdDep = Depends(get_conversation_id)
