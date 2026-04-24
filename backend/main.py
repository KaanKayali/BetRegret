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
    football_data_api_key = os.getenv("FOOTBALL_DATA_API_KEY")

    if not openai_api_key or not football_data_api_key:
        raise ValueError()

    client: MultiServerMCPClient = MultiServerMCPClient({
        "soccer_server": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [
                "./soccer-mcp-server/soccer_server.py"
            ],
            "env": {
                "FOOTBALL_DATA_API_KEY": football_data_api_key
            }
        }
    })
    
    tools: list[BaseTool] = await client.get_tools()
    allowed_tool_names = {
        "get_league_fixtures",
        "get_league_id_by_name",
        "get_team_fixtures",
        "get_team_info",
        "get_live_match_for_team",
    }
    tools = [tool for tool in tools if getattr(tool, "name", None) in allowed_tool_names]

    short_descriptions = {
        "get_league_fixtures": "Get fixtures for a league and season.",
        "get_league_id_by_name": "Find a league ID by name.",
        "get_team_fixtures": "Get past or upcoming fixtures for a team.",
        "get_team_info": "Get basic information for a team by name.",
        "get_live_match_for_team": "Check whether a team currently has a live match.",
    }
    for tool in tools:
        if getattr(tool, "name", None) in short_descriptions:
            tool.description = short_descriptions[tool.name]


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
        #"messages": [HumanMessage(content="What are the Champions League fixtures for season 2024?")]
        "messages": [HumanMessage(content="What is the team information regarding Barcelona?")]
    })
    print(answer["messages"][-1].content)
 

if __name__ == "__main__":
    asyncio.run(main())
