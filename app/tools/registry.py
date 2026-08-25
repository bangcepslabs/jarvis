from app.tools.base import JarvisTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, JarvisTool] = {}

    def register(self, tool: JarvisTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> JarvisTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[JarvisTool]:
        return list(self._tools.values())

    def get_available_tools(self) -> list[dict[str, object]]:
        return [tool.metadata.model_dump() for tool in self._tools.values()]

    def get_llm_tools(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.arguments_model.model_json_schema(),
                },
            }
            for tool in self._tools.values()
        ]

    def get_routing_hints(self) -> list[dict[str, str]]:
        return [{"name": tool.name, "routing_hint": tool.routing_hint or tool.description} for tool in self._tools.values()]

    def get_llm_tool(self, name: str) -> dict[str, object] | None:
        tool = self.get(name)
        if tool is None:
            return None
        return {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.arguments_model.model_json_schema()}}
