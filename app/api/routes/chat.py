from fastapi import APIRouter, Depends

from app.api.auth import require_client_auth
from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_client_auth)])
async def chat(request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    response = await chat_service.chat(request.message, request.conversation_id, request.response_mode)
    return ChatResponse(reply=response.reply, tool_calls=response.tool_calls, pending_action=response.pending_action)
