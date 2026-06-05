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


class GuardDecision(BaseModel):
    allowed: bool
    message: str

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
        "get_league_scorers",
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
        "get_league_scorers": "Get the top 10 scorers for a league.",
    }
    for tool in tools:
        if getattr(tool, "name", None) in short_descriptions:
            tool.description = short_descriptions[tool.name]

    current_date_str = datetime.now().strftime("%Y-%m-%d")
    llm: ChatOpenAI = ChatOpenAI(model="gpt-4o", api_key=openai_api_key)
    global guard
    guard = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=openai_api_key)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            f"You are a knowledgeable football assistant. Today's date is {current_date_str}. Use the provided soccer_server tools to answer questions about football teams, live matches, fixtures, and league data."
            "CRITICAL: The football-data.org API uses the STARTING YEAR as the season ID. For example, the 2025/2026 season must be queried with season=2025."
            "When the user mentions a team name, interpret it correctly and call the tool with the most likely official team name."
            "For example: 'Bayern Munich' should be searched as 'FC Bayern München', 'Man City' as 'Manchester City', 'PSG' as 'Paris Saint-Germain', etc."
            "If a tool call fails or returns an error (like 429 rate limit), explain the error to the user and suggest they try again later."
            "Always be precise about team names and league information. If unsure about a team name, explain to the user and ask for clarification."
            "Use the tools first and rely on them whenever they can answer the question. Only if the tools cannot answer the question at all may you fall back to internal football knowledge, and in that case you must clearly explain why the tools were not sufficient and that the answer is not tool verified."
            "if it is a prediction then only give one score instead of multiple probalitys or odds. Explain precisely your prediction and why you made that prediction to the user."
            "CRITICAL: At the very end of your response, you MUST list the names of the tools you used in this format: 'Used Tools: [tool_name1, tool_name2]'. Always do this, even if you only used one tool or if you answered from cache."
        ),
    )

agent = None
guard = None


def _strip_generation_time(text: str) -> str:
    """Remove any generation-time suffix so it is only added once by the server."""
    lines = text.splitlines()
    return "\n".join(line for line in lines if "generation time:" not in line.lower()).strip()


def _extract_used_tools(text: str) -> List[str]:
    """Extract tool names from the assistant response footer."""
    marker = "used tools:"
    for line in reversed(text.splitlines()):
        if marker in line.lower():
            start = line.find("[")
            end = line.find("]", start + 1)
            if start != -1 and end != -1 and end > start + 1:
                raw_items = line[start + 1 : end].split(",")
                return [item.strip() for item in raw_items if item.strip()]
    return []


async def _run_guard(text: str) -> GuardDecision:
    """Check whether a tool-free fallback answer stays within the football domain."""
    if guard is None:
        return GuardDecision(allowed=True, message="")

    guarded = guard.with_structured_output(GuardDecision)
    prompt = (
        "You are a light football-domain checker for a football assistant.\n"
        "Allow answers that are clearly about football, even when they rely on internal knowledge instead of tools.\n"
        "Only block answers that are clearly outside football or that introduce unrelated domains.\n"
        "If the answer is not allowed, return a short safe message in German that tells the user the assistant can only handle football topics."
        f"Text: {text}\n"
    )
    return await guarded.ainvoke(prompt)

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
    try:
        answer = await agent.ainvoke(
            {"messages": lc_messages},
            config={"callbacks": [langfuse_handler]}
        )
    except Exception as e:
        # Falls es einen Overflow Error gibt kommt eine Standart-Message
        message = str(e).lower()
        error_type = type(e).__name__.lower()
        if "context_length_exceeded" in message or "context length" in message or "openaicontextoverflowerror" in error_type:
            return ChatResponse(
                reply=(
                    "This request is too large for the model context. "
                    "Try one of these instead:\n"
                    "1. Ask about one team or one league at a time.\n"
                    "2. Ask for the next match for a specific team.\n"
                    "3. Ask for a single fixture, league, or prediction.\n"
                    "4. Start a fresh chat if the conversation has become very long."
                )
            )
        raise

    end_time = time.time()
    duration = round(end_time - start_time, 2)

    reply = _strip_generation_time(answer["messages"][-1].content)
    reply_with_time = f"{reply}\n\n*(Generation Time: {duration} seconds)*"

    used_tools = _extract_used_tools(reply)
    if not used_tools:
        reply_guard = await _run_guard(reply)
        if not reply_guard.allowed:
            return ChatResponse(reply=reply_guard.message)

    return ChatResponse(reply=reply_with_time)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
