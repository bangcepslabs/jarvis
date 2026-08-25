from app.agent.jarvis_agent import JarvisAgent
from app.agent.models import AgentResponse


class ChatService:
    def __init__(self, agent: JarvisAgent) -> None:
        self._agent = agent

    async def chat(self, message: str, conversation_id: str = "default") -> AgentResponse:
        return await self._agent.respond(message, conversation_id)
