from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import os
import re
import requests


# print(f"Python executable: {sys.executable}", file=sys.stderr)
# print(f"Python path: {sys.path}", file=sys.stderr)
print(f"Current working directory: {os.getcwd()}", file=sys.stderr)

# Handle SIGINT (Ctrl+C) gracefully
def signal_handler(sig, frame):
    print("Shutting down server gracefully...", file=sys.stderr)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Create an MCP server
mcp = FastMCP(
    name="soccer_server",
    # host="127.0.0.1",
    # port=5000,
)


def _normalize_team_name(team_name: str) -> str:
    return team_name.strip().lower()


def _normalize_team_string(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    normalized = re.sub(r"\b(fc|afc|cf|ac|a\.c\.)\b", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _team_matches_query(team: Dict[str, Any], query: str) -> bool:
    name = _normalize_team_string(team.get("name"))
    short_name = _normalize_team_string(team.get("shortName"))
    tla = _normalize_team_string(team.get("tla"))
    return query == name or query == short_name or query == tla


def _team_contains_query(team: Dict[str, Any], query: str) -> bool:
    name = _normalize_team_string(team.get("name"))
    short_name = _normalize_team_string(team.get("shortName"))
    tla = _normalize_team_string(team.get("tla"))
    return query in name or query in short_name or query == tla


def _get_team_search_results(team_name: str, headers: Dict[str, str], base_url: str) -> List[Dict[str, Any]]:
    query = _normalize_team_name(team_name)
    if not query:
        return []

    teams_url = f"{base_url}/teams"
    results: List[Dict[str, Any]] = []
    offset = 0
    page_size = 200

    while True:
        params = {"limit": page_size, "offset": offset}
        resp = requests.get(teams_url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        page_teams = data.get("teams", [])
        if not page_teams:
            break

        for team in page_teams:
            if _team_contains_query(team, query):
                results.append(team)

        if len(page_teams) < page_size:
            break
        offset += page_size
        if offset >= 2000:
            break

    return results


def _score_team_match(team: Dict[str, Any], query: str) -> int:
    name = _normalize_team_string(team.get("name"))
    short_name = _normalize_team_string(team.get("shortName"))
    tla = _normalize_team_string(team.get("tla"))
    score = 0

    if query == tla:
        score += 200
    if query == name:
        score += 100
    if query == short_name:
        score += 90
    if name.startswith(query) or short_name.startswith(query):
        score += 50
    if query in name:
        score += 20
    if query in short_name:
        score += 10
    return score


def _find_best_team(team_name: str, headers: Dict[str, str], base_url: str, teams: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    query = _normalize_team_name(team_name)
    if not query:
        return None

    if teams is None:
        teams = _get_team_search_results(team_name, headers, base_url)
    if not teams:
        return None

    exact_matches = [team for team in teams if _team_matches_query(team, query)]
    if exact_matches:
        return exact_matches[0]

    scored = sorted(teams, key=lambda team: _score_team_match(team, query), reverse=True)
    return scored[0] if scored else None


@mcp.tool()
def get_league_fixtures(league_id: int, season: int) -> Dict[str, Any]:
    """Retrieves all fixtures for a given league and season.

    Args:
        league_id (int): The ID of the league.
        season (int): The year of the season (e.g., 2023 for the 2023-2024 season).

    Returns:
        Dict[str, Any]: A dictionary containing fixture data or an error message. Key fields:
            * "response" (List[Dict[str, Any]]): A list of fixture dictionaries, as returned by the API.
            * "error" (str): An error message if the request failed.

    Example:
        ```python
        get_league_fixtures(league_id=39, season=2023)
        ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    fixtures_url = f"{base_url}/competitions/{league_id}/matches"
    fixtures_params = {"season": season}

    try:
        response = requests.get(fixtures_url, headers=headers, params=fixtures_params, timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}


@mcp.tool()
def get_league_id_by_name(league_name: str) -> Dict[str, Any]:
    """Retrieve the league ID for a given league name.

    This tool searches for a league by its name and returns its ID.  It uses the
    `/competitions` endpoint of the football-data.org API.

    **Args:**

        league_name (str): The name of the league (e.g., "Premier League", "La Liga").

    **Returns:**

        Dict[str, Any]: A dictionary containing the league ID, or an error message.  Key fields:

            *   "league_id" (int): The ID of the league, if found.
            *   "error" (str): An error message if the league is not found or an error occurs.

    **Example:**
        ```
        get_league_id_by_name(league_name="Premier League")
        # Expected output (may vary):  {"league_id": 39}
        ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        competitions_url = f"{base_url}/competitions"
        response = requests.get(competitions_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Search for the league by name
        for competition in data.get("competitions", []):
            if league_name.lower() in competition["name"].lower():
                return {"league_id": competition["id"]}

        return {"error": f"No leagues found matching '{league_name}'."}

    except Exception as e:
        return {"error": str(e)}



@mcp.tool()
def get_all_leagues_id(country: Optional[List[str]] = None) -> Dict[str, Any]:
    """Retrieve a list of all football leagues with IDs, optionally filtered by country.

    This tool retrieves a list of football leagues and their IDs. It can be filtered
    by providing a list of country names.  Uses the `/competitions` endpoint.

    **Args:**

        country (Optional[List[str]]): A list of country names to filter the leagues.
            Use ["all"] to retrieve leagues from all countries.  If None (default),
            no filtering is applied (though this is the same behavior as ["all"]).

    **Returns:**

        Dict[str, Any]:  A dictionary containing league information, or an error message. Key fields:

            *   "leagues" (Dict[str, Dict[str, Any]]):  A dictionary where keys are league names
                and values are dictionaries containing "league_id" and "country".
            *   "error" (str): An error message if the request fails.
        
        **Example:**
          ```python
          get_all_leagues_id(country = ["England", "Spain"])
          # Expected sample Output (will have many more entries):
          # {
          #     "leagues": {
          #         "Premier League": {"league_id": 39, "country": "England"},
          #         "La Liga": {"league_id": 140, "country": "Spain"},
          #          ...
          #     }
          # }
          ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        competitions_url = f"{base_url}/competitions"
        response = requests.get(competitions_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        leagues: Dict[str, Dict[str, Any]] = {}
        for competition in data.get("competitions", []):
            league_name = competition["name"]
            league_id = competition["id"]
            league_country = competition["area"]["name"]

            if country and "all" not in country:
                if league_country.lower() not in [c.lower() for c in country]:
                    continue

            leagues[league_name] = {
                "league_id": league_id,
                "country": league_country
            }

        return {"leagues": leagues}

    except Exception as e:
        return {"error": str(e)}



@mcp.tool()
def get_standings(league_id: Optional[List[int]], season: List[int], team: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve league standings for multiple leagues and seasons, optionally filtered by team.

    This tool retrieves the standings table for one or more leagues, across multiple
    seasons. It can optionally filter the results to show standings for a specific team.
    Uses the `/standings` endpoint.

    **Args:**

        league_id (Optional[List[int]]): A list of league IDs to retrieve standings for.
        season (List[int]): A list of 4-digit season years (e.g., [2021, 2022]).
        team (Optional[int]):  A specific team ID to filter the standings.

    **Returns:**

        Dict[str, Any]: A dictionary containing the standings, or an error message.  The structure is:

            *   `{league_id: {season: standings_data}}`

            `standings_data` is the raw JSON response from the API for the given league and season.  If an error occurs
            for a specific league/season, the `standings_data` will be `{"error": "error message"}`.

        **Example:**

          ```python
            get_standings(league_id=[39, 140], season=[2022, 2023], team=None)
          ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    results: Dict[int, Dict[int, Any]] = {}
    leagues = league_id if league_id else []

    for league in leagues:
        results[league] = {}
        for year in season:
            url = f"{base_url}/competitions/{league}/standings"
            params = {"season": year}

            if team is not None:
                params["team"] = team

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                results[league][year] = response.json()
            except Exception as e:
                results[league][year] = {"error": str(e)}

    return results

    for league in leagues:
        results[league] = {}
        for year in season:
            url = f"{base_url}/standings"
            params = {"season": year, "league": league}

            if team is not None:
                params["team"] = team

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                results[league][year] = response.json()
            except Exception as e:
                results[league][year] = {"error": str(e)}

    return results

@mcp.tool()
def get_player_id(player_name: str) -> Dict[str, Any]:
    """Retrieve a list of player IDs and identifying information for players matching a given name.

    This tool searches for players by either their first *or* last name and returns a list of
    potential matches.  It includes identifying information to help disambiguate players.
    Uses the `/players/profiles` endpoint.

    **Args:**

        player_name (str): The first *or* last name of the player (e.g., "Lionel" or "Messi").
                           Do *not* provide both first and last names.  The name must be at least
                           3 characters long.

    **Returns:**

        Dict[str, Any]: A dictionary containing a list of players or an error message. Key fields:
            * "players" (List[Dict[str, Any]]): A list of dictionaries, each representing a player.
              Each player dictionary includes:
                * "player_id" (int): The player's ID.
                * "firstname" (str): The player's first name.
                * "lastname" (str): The player's last name.
                * "age" (int): The player's age.
                * "nationality" (str): The player's nationality.
                * "birth_date" (str): The player's birth date (YYYY-MM-DD).
                * "birth_place" (str): The player's birth place.
                *  "birth_country" (str)
                * "height" (str): The player's height (e.g., "170 cm").
                * "weight" (str): The player's weight (e.g., "68 kg").
            * "error" (str): An error message if no players are found or an error occurs.

    **Example:**
        ```
        get_player_id(player_name="Messi")
        ```

    """
    if " " in player_name.strip():
        return {"error": "Please enter only the first *or* last name, not both."}
    if len(player_name.strip()) < 3:
         return {"error": "The name must be at least 3 characters long."}


    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key,
    }
    # Note: football-data.org doesn't have a direct player search endpoint
    # This tool is limited and may not work as expected
    url = f"{base_url}/persons"
    params = {
        "name": player_name,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("persons"):
            return {"error": f"No players found matching '{player_name}'."}

        player_list = []
        for person in data["persons"]:
            player_info = {
                "player_id": person.get("id"),
                "firstname": person.get("firstName"),
                "lastname": person.get("lastName"),
                "nationality": person.get("nationality"),
                "dateOfBirth": person.get("dateOfBirth"),
            }
            player_list.append(player_info)

        return {"players": player_list}

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}






@mcp.tool()
def get_team_fixtures(team_name: str, type: str = "upcoming", limit: int = 5) -> Dict[str, Any]:
    """Given a team name, returns either the last N or the next N fixtures for that team.

    **Args:**

        team_name (str): The team's name to search for. Must be >= 3 characters.
        type (str, optional): Either 'past' or 'upcoming' fixtures. Defaults to 'upcoming'.
        limit (int, optional): How many fixtures to retrieve.  Defaults to 5.

    **Returns:**

        Dict[str, Any]: A dictionary containing the fixture data or an error message. Key fields:
            * "response" (List[Dict[str,Any]]): List of fixtures, if found.
            * "error" (str): Error message if the request failed, or the team wasn't found.

        The structure of each fixture in `response` is the raw JSON response from the API.

    **Example:**

        ```python
        get_team_fixtures(team_name="Manchester United", type="past", limit=3)
        ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
        return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No teams found matching '{team_name}'."}

        team_id = team["id"]
        fixtures_url = f"{base_url}/teams/{team_id}/matches"
        fixtures_params = {"limit": limit}

        if type.lower() == "past":
            fixtures_params["status"] = "FINISHED"
        elif type.lower() == "upcoming":
            fixtures_params["status"] = "SCHEDULED"
        else:
            return {"error": "The 'type' parameter must be either 'past' or 'upcoming'."}

        fixtures_resp = requests.get(fixtures_url, headers=headers, params=fixtures_params, timeout=15)
        fixtures_resp.raise_for_status()
        return fixtures_resp.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_fixture_statistics(fixture_id: int) -> Dict[str, Any]:
    """Retrieves detailed statistics for a specific fixture (game).

    **Args:**

        fixture_id (int): The numeric ID of the fixture/game.

    **Returns:**

        Dict[str, Any]:  A dictionary containing fixture statistics or an error message.  Key fields:
            * "response" (List[Dict[str, Any]]): List of team statistics, if found.
            * "error" (str): Error message, if any occurred.

        The structure of the data within `response` is the raw API response.

    **Example:**

    ```python
    get_fixture_statistics(fixture_id=867946)
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    url = f"{base_url}/matches/{fixture_id}"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_team_fixtures_by_date_range(team_name: str, from_date: str, to_date: str, season: str) -> Dict[str, Any]:
    """Retrieve all fixtures for a given team within a date range.

    **Args:**

        team_name (str): Team name to search for (e.g. 'Arsenal', 'Barcelona').
        from_date (str): Start date in YYYY-MM-DD format (e.g. '2023-08-01').
        to_date (str): End date in YYYY-MM-DD format (e.g. '2023-08-31').
        season (str):  Season in YYYY format.

    **Returns:**
        Dict[str, Any]: A dictionary containing the fixture data or an error message. Key fields:
            * "response" (List[Dict[str, Any]]):  A list of fixture dictionaries.
            * "error" (str): An error message.

        The structure of each dictionary in `response` is the raw API response.

    **Example:**

        ```python
        get_team_fixtures_by_date_range(
            team_name="Liverpool", from_date="2023-09-01", to_date="2023-09-30", season="2023"
        )
        ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
        return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No teams found matching '{team_name}'."}

        team_id = team["id"]
        fixtures_url = f"{base_url}/teams/{team_id}/matches"
        fixtures_params = {
            "dateFrom": from_date,
            "dateTo": to_date
        }

        fixtures_resp = requests.get(fixtures_url, headers=headers, params=fixtures_params, timeout=15)
        fixtures_resp.raise_for_status()
        return fixtures_resp.json()

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_fixture_events(fixture_id: int) -> Dict[str, Any]:
    """Retrieves all in-game events for a given fixture ID (e.g. goals, cards, subs).

    **Args:**

        fixture_id (int): Numeric ID of the fixture whose events you want.

    **Returns:**

        Dict[str, Any]: A dictionary containing the fixture events or an error message. Key fields:
            * "response" (List[Dict[str, Any]]): List of events, if found.
            * "error" (str): Error message if the request failed.

        The structure of the data within `response` is the raw API response.

    **Example:**

    ```python
    get_fixture_events(fixture_id=867946)
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    url = f"{base_url}/matches/{fixture_id}"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}



@mcp.tool()
def get_league_schedule_by_date(league_name: str, date: List[str], season: str) -> Dict[str, Any]:
    """Retrieves the schedule (fixtures) for a given league on one or multiple specified dates.

    **Args:**

        league_name (str): Name of the league (e.g., 'Premier League', 'La Liga').
        date (List[str]): List of dates in YYYY-MM-DD format (e.g., ['2024-03-08', '2024-03-09']).
        season (str): Season in YYYY format (e.g., '2023').

    **Returns:**

        Dict[str, Any]: A dictionary where each key is a date from the input `date` list,
            and the value is the API response for that date, or an error message.

    **Example:**

    ```python
    get_league_schedule_by_date(
        league_name="Premier League", date=["2024-03-08", "2024-03-09"], season="2023"
    )
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(league_name.strip()) < 3:
        return {"error": "The league name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    # Step 1: Get league ID by searching name
    try:
        leagues_url = f"{base_url}/competitions"
        resp = requests.get(leagues_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("competitions"):
            return {"error": f"No leagues found."}

        # Find the correct league
        league_id = None
        for competition in data["competitions"]:
             if competition["name"].lower() == league_name.lower():
                league_id = competition["id"]
                break

        if not league_id:
            return {"error": f"No league found matching '{league_name}'."}

        # Step 2: Fetch fixtures for each date
        combined_results = {}
        for d in date:
            try:
                fixtures_url = f"{base_url}/competitions/{league_id}/matches"
                fixtures_params = {"dateFrom": d, "dateTo": d}
                resp = requests.get(fixtures_url, headers=headers, params=fixtures_params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                combined_results[d] = data
            except requests.exceptions.RequestException as e:
                combined_results[d] = {"error": f"Request failed: {e}"}
            except Exception as e:
                combined_results[d] = {"error": f"An unexpected error occurred: {e}"}

        return combined_results

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_live_match_for_team(team_name: str) -> Dict[str, Any]:
    """Checks if a given team is currently playing live.

    **Args:**

        team_name (str): The team's name. Example: 'Arsenal'. Must be >= 3 chars.

    **Returns:**

        Dict[str, Any]:  If a live match is found, returns a dictionary with a "live_fixture"
            key containing the fixture data. If no live match is found, returns a dictionary
            with a "message" key. If an error occurs, returns a dictionary with an "error" key.

    **Example:**

    ```python
    get_live_match_for_team(team_name="Chelsea")
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
        return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    # Step 1: find team ID
    try:
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Step 2: check for live matches
        fixtures_resp = requests.get(
            f"{base_url}/teams/{team_id}/matches",
            headers=headers,
            params={"status": "LIVE"},
            timeout=15
        )
        fixtures_resp.raise_for_status()
        fixtures_data = fixtures_resp.json()

        if fixtures_data.get("matches"):
            return {"live_fixture": fixtures_data["matches"][0]}
        else:
            return {"message": f"No live match found for '{team_name}'."}

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_live_stats_for_team(team_name: str) -> Dict[str, Any]:
    """Retrieves live in-game stats for a team currently in a match.

    **Args:**
        team_name (str): Team name to get live stats for. e.g., 'Arsenal'.

    **Returns:**

        Dict[str, Any]:  If the team is playing live, returns a dictionary containing
            the `fixture_id` and `live_stats`.  If no live match is found, returns
            a dictionary with a "message" key.  If an error occurs, returns a dictionary
            with an "error" key.

    **Example:**

    ```python
    get_live_stats_for_team(team_name="Liverpool")
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
        return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        # Step 1: get team ID
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Step 2: check for live fixtures
        fixtures_resp = requests.get(
            f"{base_url}/teams/{team_id}/matches",
            headers=headers,
            params={"status": "LIVE"},
            timeout=15
        )
        fixtures_resp.raise_for_status()
        fixtures_data = fixtures_resp.json()

        if fixtures_data.get("matches"):
            live_match = fixtures_data["matches"][0]
            return {"fixture_id": live_match["id"], "live_stats": live_match}
        else:
            return {"message": f"No live match found for '{team_name}'."}

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_live_match_timeline(team_name: str) -> Dict[str, Any]:
    """Retrieves the real-time timeline of events for a team's current live match.

    **Args:**

        team_name (str): Team name.

    **Returns:**

        Dict[str, Any]: If the team is playing live, returns a dictionary containing
            `fixture_id` and `timeline_events`. If not, returns a dictionary with a "message" key.
            If an error occurs, it returns a dictionary with an "error" key.

    **Example:**

    ```python
    get_live_match_timeline(team_name="Manchester City")
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
        return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        # Step 1: team ID
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Step 2: check live fixtures
        fixtures_resp = requests.get(
            f"{base_url}/teams/{team_id}/matches",
            headers=headers,
            params={"status": "LIVE"},
            timeout=15
        )
        fixtures_resp.raise_for_status()
        fixtures_data = fixtures_resp.json()

        if fixtures_data.get("matches"):
            live_match = fixtures_data["matches"][0]
            return {"fixture_id": live_match["id"], "timeline_events": live_match}
        else:
            return {"message": f"No live match found for '{team_name}'."}

    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

@mcp.tool()
def get_league_info(league_name: str) -> Dict[str, Any]:
    """Retrieve information about a specific football league.

    **Args:**

        league_name (str): Name of the league (e.g., 'Champions League').

    **Returns:**

        Dict[str, Any]:  A dictionary containing league information or an error message.  Key fields:
            *  "response" (List[Dict[str,Any]]): A list of leagues that match the search, if found.
            *  "error" (str): An error message if the request fails or no leagues are found.

        The structure of data in "response" is the raw API response.

    **Example:**

    ```python
    get_league_info(league_name="Premier League")
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(league_name.strip()) < 3:
        return {"error": "The league name must be at least 3 characters long."}


    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    # Fetch league information
    league_url = f"{base_url}/competitions"
    try:
        resp = requests.get(league_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("competitions"):
          return {"error": f"No leagues found."}
        
        # Find matching league
        for competition in data["competitions"]:
            if competition["name"].lower() == league_name.lower():
                return {"response": [competition]}
        
        return {"error": f"No league found matching '{league_name}'."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}


@mcp.tool()
def get_team_info(team_name: str) -> Dict[str, Any]:
    """Retrieve basic information about a specific football team.

    **Args:**

        team_name (str): Name of the team (e.g., 'Manchester United').

    **Returns:**
        Dict[str, Any]: A dictionary containing team information or an error message. Key fields:
          * "response" (List[Dict[str,Any]]): List of teams that match the search name.
          * "error" (str): If the API request failed or the team is not found.

        The structure of data in "response" is the raw API response.
    **Example:**

    ```python
    get_team_info(team_name="Real Madrid")
    ```
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}
    if len(team_name.strip()) < 3:
      return {"error": "The team name must be at least 3 characters long."}

    base_url = "https://api.football-data.org/v4"
    headers = {
        "X-Auth-Token": api_key
    }

    try:
        teams = _get_team_search_results(team_name, headers, base_url)
        if not teams:
            return {"error": f"No team found matching '{team_name}'."}
        best_team = _find_best_team(team_name, headers, base_url, teams)
        return {"response": teams, "best_match": best_team}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}
  

if __name__ == "__main__":
    try:
        print("Starting MCP server 'soccer_server' on 127.0.0.1:5000", file=sys.stderr)
        # Use this approach to keep the server running
        mcp.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        # Sleep before exiting to give time for error logs
        time.sleep(5)