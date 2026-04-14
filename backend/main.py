import asyncio
import sys
from langchain_core.tools.base import BaseTool
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from dotenv import load_dotenv


async def main() -> None:
    load_dotenv()
    
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    rapid_api_key_football = os.getenv("RAPID_API_KEY_FOOTBALL")

    if not openai_api_key or not rapid_api_key_football:
        raise ValueError()

    client: MultiServerMCPClient = MultiServerMCPClient({
        "soccer_server": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [
                "./soccer-mcp-server/soccer_server.py"
            ],
            "env": {
                "RAPID_API_KEY_FOOTBALL": rapid_api_key_football
            }
        }
    })
    
    tools: list[BaseTool] = await client.get_tools()



    llm: ChatOpenAI = ChatOpenAI(
        model="gpt-5.4",
        api_key=openai_api_key
    )

    llm_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="You are a code agent and you are providing informations about football (soccer) based on the soccer_server functions. Evaluate based on the soccer_server tools provided"
    )



    answer = await llm_agent.ainvoke({
        "messages": [HumanMessage(content="What are the Champions League fixtures for season 2024?")]
    })
    print(answer["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
