import asyncio
import os
import sys
import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_core.tools.base import BaseTool
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langfuse.langchain import CallbackHandler
from typing import List

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Globaler Agent
    global agent
    agent = await build_agent()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class ChatResponse(BaseModel):
    reply: str

# Agent-Konfiguration und Tool-Anbindung
async def build_agent():
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    football_data_api_key = os.getenv("FOOTBALL_DATA_API_KEY")

    if not openai_api_key or not football_data_api_key:
        raise ValueError("OPENAI_API_KEY and FOOTBALL_DATA_API_KEY must be set")

    client: MultiServerMCPClient = MultiServerMCPClient({
        "soccer_server": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["./soccer-mcp-server/soccer_server.py"],
            "env": {"FOOTBALL_DATA_API_KEY": football_data_api_key},
        }
    })

    # Tools vom MCP-Server laden
    tools: list[BaseTool] = await client.get_tools()
    
    # Filter für erlaubte Tools
    allowed_tool_names = {
        "get_league_fixtures",
        "get_league_id_by_name",
        "get_team_fixtures",
        "get_team_info",
        "get_live_match_for_team",
        "predict_match_outcome",
    }
    tools = [tool for tool in tools if getattr(tool, "name", None) in allowed_tool_names]

    # Kurzbeschreibungen für den Agenten
    short_descriptions = {
        "get_league_fixtures": "Get fixtures for a league and season.",
        "get_league_id_by_name": "Find a league ID by name.",
        "get_team_fixtures": "Get past or upcoming fixtures for a team.",
        "get_team_info": "Get basic information for a team by name.",
        "get_live_match_for_team": "Check whether a team currently has a live match.",
        "predict_match_outcome": "Predict the outcome and betting probabilities for a match between two teams.",
    }
    for tool in tools:
        if getattr(tool, "name", None) in short_descriptions:
            tool.description = short_descriptions[tool.name]

    current_date_str = datetime.now().strftime("%Y-%m-%d")
    llm: ChatOpenAI = ChatOpenAI(model="gpt-4.1", api_key=openai_api_key)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            f"You are a knowledgeable football assistant. Today's date is {current_date_str}. Use the provided soccer_server tools to answer questions about football teams, live matches, fixtures, and league data."
            "CRITICAL: The football-data.org API uses the STARTING YEAR as the season ID. Today is 2026-05-10, so the current season is 2025/2026. Therefore, use 2025 as the 'season' parameter for current league fixtures or standings."
            "When the user mentions a team name, interpret it correctly and call the tool with the most likely official team name."
            "For example: 'Bayern Munich' should be searched as 'FC Bayern München', 'Man City' as 'Manchester City', 'PSG' as 'Paris Saint-Germain', etc."
            "If a tool call fails or returns an error (like 429 rate limit), explain the error to the user and suggest they try again later."
            "Always be precise about team names and league information. If unsure about a team name, explain to the user and ask for clarification."
            "if you dont find the answer from the tools then say that you are not able to find the answer from the tools and then try to find the answer from your own internal knowledge base and try to be precise so the user can win with your betting predictions but first always try to find the answer from the tools"
            "if it is a prediction then only give one score instead of multiple probalitys or odds. Explain precisely your prediction and why you made that prediction to the user. Give the details the tools gave you."
            "list the used tool names for each prompt after every response"
        ),
    )

agent = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if agent is None:
        raise RuntimeError("Agent not initialized")

    # Chat-Verlauf für LangChain aufbereiten
    lc_messages = []
    for msg in req.messages:
        if msg.role == "HumanMessage":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "AIMessage":
            lc_messages.append(AIMessage(content=msg.content))

    start_time = time.time()
    
    # Monitoring via Langfuse
    langfuse_handler = CallbackHandler()
    answer = await agent.ainvoke(
        {"messages": lc_messages},
        config={"callbacks": [langfuse_handler]}
    )
    
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    
    reply = answer["messages"][-1].content
    reply_with_time = f"{reply}\n\n*(Generation Time: {duration} seconds)*"
    
    return ChatResponse(reply=reply_with_time)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
