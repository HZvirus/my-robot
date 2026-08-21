"""Agent 端点:非流式 run + 推理步痕迹。"""
from anyio import to_thread
from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.core.rbac import Principal
from app.models.agent import AgentRunRequest, AgentRunResponse, AgentStepOut
from app.services.agent_service import agent_service

router = APIRouter()


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(
    req: AgentRunRequest, principal: Principal = CurrentUser
) -> AgentRunResponse:
    try:
        return await agent_service.run(req.message, req.conversation_id, principal.user_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权访问该会话") from None


@router.get("/agent/steps/{conversation_id}", response_model=list[AgentStepOut])
async def agent_steps(
    conversation_id: str, principal: Principal = CurrentUser
) -> list[AgentStepOut]:
    try:
        return await to_thread.run_sync(
            agent_service.list_steps, conversation_id, principal.user_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="会话不存在") from None