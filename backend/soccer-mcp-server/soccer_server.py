from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
import math
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import os
import re
import unicodedata
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# print(f"Python executable: {sys.executable}", file=sys.stderr)
# print(f"Python path: {sys.path}", file=sys.stderr)
print(f"Current working directory: {os.getcwd()}", file=sys.stderr)

# Server bei Strg+C sauber beenden
def signal_handler(sig, frame):
    print("Shutting down server gracefully...", file=sys.stderr)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# MCP-Server initialisieren
mcp = FastMCP(
    name="soccer_server",
    # host="127.0.0.1",
    # port=5000,
)

REQUEST_SESSION = requests.Session()
RETRY_STRATEGY = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    backoff_factor=1,
    raise_on_status=False,
)
ADAPTER = HTTPAdapter(max_retries=RETRY_STRATEGY)
REQUEST_SESSION.mount("https://", ADAPTER)
REQUEST_SESSION.mount("http://", ADAPTER)

TEAM_SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}
COMPETITIONS_CACHE: Optional[Dict[str, Any]] = None
TEAM_ID_CACHE: Dict[str, Dict[str, Any]] = {}
TEAM_FULL_DATA_CACHE: Dict[int, Dict[str, Any]] = {}
STANDINGS_DATA_CACHE: Dict[int, Dict[str, Any]] = {}


def _normalize_string(value: Optional[str]) -> str:
    """Bereitet einen String für den Vergleich vor (Kleinbuchstaben, keine Sonderzeichen, keine FC-Kürzel)."""
    if not value:
        return ""

    normalized = value.strip().lower()

    # Akzente entfernen
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")

    # Sonderzeichen entfernen
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    # Fussball-Kürzel entfernen
    normalized = re.sub(r"\b(fc|afc|cf|ac|a\.c\.|ssc|as|rb|rsc|vfl|bvb)\b", "", normalized)
    # Doppelte Leerzeichen normalisieren
    return re.sub(r"\s+", " ", normalized).strip()


def _team_matches_query(team: Dict[str, Any], query: str) -> bool:
    name = _normalize_string(team.get("name"))
    short_name = _normalize_string(team.get("shortName"))
    tla = _normalize_string(team.get("tla"))
    return query == name or query == short_name or query == tla


def _team_contains_query(team: Dict[str, Any], query: str) -> bool:
    name = _normalize_string(team.get("name"))
    short_name = _normalize_string(team.get("shortName"))
    tla = _normalize_string(team.get("tla"))
    return query in name or query in short_name or query == tla


# JSON von API abrufen mit Retry-Logik bei Rate-Limits
def _fetch_json(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = REQUEST_SESSION.get(url, headers=headers, params=params, timeout=timeout)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2 # Wartezeit bei API-Limit (429)
                    print(f"Rate limited (429). Waiting {wait_time}s and retrying...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries - 1 and response.status_code == 429:
                continue
            raise e
    return {}


def _get_competitions(headers: Dict[str, str], base_url: str) -> Dict[str, Any]:
    global COMPETITIONS_CACHE
    if COMPETITIONS_CACHE is not None:
        return COMPETITIONS_CACHE

    competitions_url = f"{base_url}/competitions"
    COMPETITIONS_CACHE = _fetch_json(competitions_url, headers, timeout=15)
    return COMPETITIONS_CACHE


def _get_team_search_results(team_name: str, headers: Dict[str, str], base_url: str) -> List[Dict[str, Any]]:
    query = _normalize_string(team_name)
    if not query:
        return []

    if query in TEAM_SEARCH_CACHE:
        return TEAM_SEARCH_CACHE[query]

    teams_url = f"{base_url}/teams"
    results: List[Dict[str, Any]] = []
    offset = 0
    page_size = 200

    while True:
        params = {"limit": page_size, "offset": offset}
        data = _fetch_json(teams_url, headers, params=params, timeout=15)
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

    TEAM_SEARCH_CACHE[query] = results
    return results


def _score_team_match(team: Dict[str, Any], query: str) -> int:
    name = _normalize_string(team.get("name"))
    short_name = _normalize_string(team.get("shortName"))
    tla = _normalize_string(team.get("tla"))
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


# Bestes passendes Team aus Suchergebnissen finden
def _find_best_team(team_name: str, headers: Dict[str, str], base_url: str, teams: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    query = _normalize_string(team_name)
    if not query:
        return None

    if query in TEAM_ID_CACHE:
        return TEAM_ID_CACHE[query]

    if teams is None:
        print(f"Waiting 20s before searching for team: {team_name}...", file=sys.stderr)
        time.sleep(20)
        teams = _get_team_search_results(team_name, headers, base_url)
    if not teams:
        return None

    exact_matches = [team for team in teams if _team_matches_query(team, query)]
    best_team = exact_matches[0] if exact_matches else (sorted(teams, key=lambda team: _score_team_match(team, query), reverse=True)[0] if teams else None)
    if best_team:
        TEAM_ID_CACHE[query] = best_team
    return best_team


# Tabellendaten eines Teams abrufen (Position, PPG, GD)
def _get_team_standings_data(team_name: str, headers: Dict[str, str], base_url: str) -> Optional[Dict[str, Any]]:
    team = _find_best_team(team_name, headers, base_url)
    if not team:
        return None
    
    team_id = team['id']

    # Wettbewerbe des Teams abrufen
    if team_id in TEAM_FULL_DATA_CACHE:
        print(f"[CACHE HIT] Team data for {team_name}", file=sys.stderr)
        team_data = TEAM_FULL_DATA_CACHE[team_id]
    else:
        # Nur warten, wenn wir wirklich ins Netz müssen
        print(f"[API REQUEST] Fetching team data for {team_name}...", file=sys.stderr)
        print(f"Waiting 20s before fetching team data for {team_name}...", file=sys.stderr)
        time.sleep(20)
        team_data = _fetch_json(f"{base_url}/teams/{team_id}", headers)
        TEAM_FULL_DATA_CACHE[team_id] = team_data
    
    # Erste verfügbare Liga mit Tabelle finden
    for comp in team_data.get('runningCompetitions', []):
        if comp.get('type') not in ['LEAGUE', 'CUP']: # We prefer leagues for better stats
            continue
            
        comp_id = comp['id']
        if comp_id in STANDINGS_DATA_CACHE:
            print(f"[CACHE HIT] Standings for competition {comp_id}", file=sys.stderr)
            standings = STANDINGS_DATA_CACHE[comp_id]
        else:
            # Nur warten, wenn wir wirklich ins Netz müssen
            print(f"[API REQUEST] Fetching standings for {comp_id}...", file=sys.stderr)
            print(f"Waiting 20s before fetching standings...", file=sys.stderr)
            time.sleep(20)
            try:
                standings = _fetch_json(f"{base_url}/competitions/{comp_id}/standings", headers)
                STANDINGS_DATA_CACHE[comp_id] = standings
            except:
                continue
        
        for s in standings.get('standings', []):
            if s.get('type') == 'TOTAL': # Gesamttabelle verwenden
                for entry in s.get('table', []):
                    if entry['team']['id'] == team_id:
                        return {
                            "team_name": entry['team']['name'],
                            "team_id": team_id,
                            "position": entry['position'],
                            "playedGames": entry['playedGames'],
                            "points": entry['points'],
                            "goalsFor": entry['goalsFor'],
                            "goalsAgainst": entry['goalsAgainst'],
                            "goalDifference": entry['goalDifference'],
                            "league_name": comp['name']
                        }
    return None


@mcp.tool()
def get_league_scorers(league_id: int) -> Dict[str, Any]:
    """Retrieves the top scorers for a given league.
    
    Args:
        league_id (int): The ID of the league (e.g., 2021 for Premier League).
        
    Returns:
        Dict[str, Any]: A list of top scorers with their team and goal count.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    headers = {"X-Auth-Token": api_key}
    base_url = "https://api.football-data.org/v4"
    
    try:
        data = _fetch_json(f"{base_url}/competitions/{league_id}/scorers", headers)
        scorers = []
        for s in data.get('scorers', [])[:10]: # Top 10
            scorers.append({
                "player": s['player']['name'],
                "team": s['team']['name'],
                "goals": s['goals'],
                "assists": s.get('assists', 0)
            })
        return {"scorers": scorers}
    except Exception as e:
        return {"error": f"Could not fetch scorers: {e}"}


@mcp.tool()
def get_league_fixtures(league_id: int, season: int) -> Dict[str, Any]:
    """Retrieves all fixtures for a given league and season.

    Args:
        league_id (int): The ID of the league.
        season (int): The year of the season (e.g., 2025 for the 2025-2026 season).

    Returns:
        Dict[str, Any]: A dictionary containing fixture data or an error message. Key fields:
            * "response" (List[Dict[str, Any]]): A list of fixture dictionaries, as returned by the API.
            * "error" (str): An error message if the request failed.

    Example:
        ```python
        get_league_fixtures(league_id=39, season=202)
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
        data = _get_competitions(headers, base_url)

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
        data = _get_competitions(headers, base_url)

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

    # Schritt 1: Liga-ID über den Namen suchen
    try:
        leagues_url = f"{base_url}/competitions"
        resp = requests.get(leagues_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("competitions"):
            return {"error": f"No leagues found."}

        # Die richtige Liga in der Liste finden
        league_id = None
        for competition in data["competitions"]:
             if competition["name"].lower() == league_name.lower():
                league_id = competition["id"]
                break

        if not league_id:
            return {"error": f"No league found matching '{league_name}'."}

        # Schritt 2: Spiele für jedes Datum abrufen
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

    # Schritt 1: Team-ID finden
    try:
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Schritt 2: Auf Live-Spiele prüfen
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
        # Schritt 1: Team-ID abrufen
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Schritt 2: Nach Live-Begegnungen suchen
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
        # Schritt 1: Team-ID ermitteln
        team = _find_best_team(team_name, headers, base_url)
        if not team:
            return {"error": f"No team found matching '{team_name}'."}
        team_id = team["id"]

        # Schritt 2: Live-Spielplan prüfen
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

    # Liga-Informationen von API laden
    league_url = f"{base_url}/competitions"
    try:
        resp = requests.get(league_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("competitions"):
          return {"error": f"No leagues found."}
        
        # Passende Liga finden
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
  

@mcp.tool()
def predict_match_outcome(team_home_name: str, team_away_name: str) -> Dict[str, Any]:
    """Predicts the outcome of a football match between two teams.
    Analyzes their current league statistics, points per game, and goal differences 
    to calculate win, draw, and loss probabilities.

    Args:
        team_home_name (str): Name of the home team (e.g., 'Arsenal').
        team_away_name (str): Name of the away team (e.g., 'Liverpool').

    Returns:
        Dict[str, Any]: A dictionary containing probabilities, analysis, and a betting recommendation.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    if not api_key:
        return {"error": "FOOTBALL_DATA_API_KEY environment variable not set."}

    base_url = "https://api.football-data.org/v4"
    headers = {"X-Auth-Token": api_key}

    try:
        # Heimteam-Statistiken laden
        home_stats = _get_team_standings_data(team_home_name, headers, base_url)
        if not home_stats:
            return {"error": f"Could not find league stats for home team: {team_home_name}"}

        # Auswärtsteam-Statistiken laden
        away_stats = _get_team_standings_data(team_away_name, headers, base_url)
        if not away_stats:
            return {"error": f"Could not find league stats for away team: {team_away_name}"}

        # Calculation logic (average values per game)
        def calculate_team_metrics(stats):
            games_played = stats['playedGames']
            if games_played == 0:
                return 1.0, 0.0, 1.0, 1.0 # Default stats for a new season
            
            avg_points_per_game = stats['points'] / games_played
            avg_goal_diff_per_game = stats['goalDifference'] / games_played
            avg_goals_scored_per_game = stats['goalsFor'] / games_played
            avg_goals_conceded_per_game = stats['goalsAgainst'] / games_played
            return avg_points_per_game, avg_goal_diff_per_game, avg_goals_scored_per_game, avg_goals_conceded_per_game

        ppg_home, gd_home, goals_home_avg, conceded_home_avg = calculate_team_metrics(home_stats)
        ppg_away, gd_away, goals_away_avg, conceded_away_avg = calculate_team_metrics(away_stats)

        # Power Score (70% Form/Points, 30% Goal Difference) + Home Advantage
        power_score_home = (ppg_home * 0.7) + (gd_home * 0.3) + 0.2
        power_score_away = (ppg_away * 0.7) + (gd_away * 0.3)

        # Expected Goals (based on attack vs. opponent's defense)
        expected_goals_home = (goals_home_avg * 0.6) + (conceded_away_avg * 0.4) + 0.1
        expected_goals_away = (goals_away_avg * 0.6) + (conceded_home_avg * 0.4)

        # Calculate probabilities (Sigmoid model)
        strength_diff = power_score_home - power_score_away
        
        # Base win probabilities
        prob_win_base_home = 1 / (1 + math.exp(-strength_diff))
        prob_win_base_away = 1 - prob_win_base_home
        
        # Draw factor (higher when teams are equally strong)
        draw_factor = 0.25 * math.exp(-abs(strength_diff) * 2)
        
        # Final probabilities in percent
        prob_home_percent = round(prob_win_base_home * (1 - draw_factor) * 100, 1)
        prob_away_percent = round(prob_win_base_away * (1 - draw_factor) * 100, 1)
        prob_draw_percent = round(draw_factor * 100, 1)

        # Score prediction (realistically rounded)
        predicted_score_home = round(expected_goals_home)
        predicted_score_away = round(expected_goals_away)
        
        # Prevent identical scores if there is a significant strength difference
        if predicted_score_home == predicted_score_away and abs(strength_diff) > 0.5:
            if strength_diff > 0: predicted_score_home += 1
            else: predicted_score_away += 1

        recommendation = "Home Win" if prob_home_percent > prob_away_percent + 10 else ("Away Win" if prob_away_percent > prob_home_percent + 10 else "Draw / Close Match")

        return {
            "prediction": {
                "home_team": home_stats['team_name'],
                "away_team": away_stats['team_name'],
                "expected_score": f"{predicted_score_home}-{predicted_score_away}",
                "probabilities": {
                    "home_win": f"{prob_home_percent}%",
                    "draw": f"{prob_draw_percent}%",
                    "away_win": f"{prob_away_percent}%"
                },
                "recommendation": recommendation,
                "analysis": {
                    "home_league": home_stats['league_name'],
                    "home_ppg": round(ppg_home, 2),
                    "home_gfpg": round(goals_home_avg, 2),
                    "home_gapg": round(conceded_home_avg, 2),
                    "away_league": away_stats['league_name'],
                    "away_ppg": round(ppg_away, 2),
                    "away_gfpg": round(goals_away_avg, 2),
                    "away_gapg": round(conceded_away_avg, 2)
                }
            }
        }

    except Exception as e:
        return {"error": f"Prediction failed: {str(e)}"}


if __name__ == "__main__":
    try:
        print("Starting MCP server 'soccer_server' on 127.0.0.1:5000", file=sys.stderr)
        # Server dauerhaft laufen lassen
        mcp.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        # Sleep before exiting to give time for error logs
        time.sleep(5)
