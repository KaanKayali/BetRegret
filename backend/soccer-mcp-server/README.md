[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/obinopaul-soccer-mcp-server-badge.png)](https://mseep.ai/app/obinopaul-soccer-mcp-server)

# Soccer MCP Server

A Python server implementing Model Context Protocol (MCP) for football (soccer) statistics and live match data using the API-Football service.

## Overview

This server provides a comprehensive set of tools for accessing football data through the API-Football API. It serves as a bridge between applications and football data services, offering both live match information and historical statistics for leagues, teams, and players worldwide.

## Features

- League data (standings, fixtures, schedules)
- Team information and fixtures
- Player statistics and profiles
- Live match data (events, statistics, timelines)
- Match analysis (statistics, events)

## Configuration

This server requires an API key from RapidAPI for the API-Football service:

1. Create an account on [RapidAPI](https://rapidapi.com/)
2. Subscribe to the [API-Football API](https://rapidapi.com/api-sports/api/api-football/)
3. Set the environment variable:
   ```
   RAPID_API_KEY_FOOTBALL=your_api_key_here
   ```

## Tools

### League Data

- **get_league_id_by_name**
  - Retrieve the league ID for a given league name
  - Example: `get_league_id_by_name(league_name="Premier League")`

- **get_all_leagues_id**
  - Retrieve a list of all football leagues with IDs
  - Can be filtered by country
  - Example: `get_all_leagues_id(country=["England", "Spain"])`

- **get_standings**
  - Retrieve league standings for multiple leagues and seasons
  - Can be filtered by team
  - Example: `get_standings(league_id=[39, 140], season=[2022, 2023])`

- **get_league_info**
  - Retrieve information about a specific football league
  - Example: `get_league_info(league_name="Champions League")`

- **get_league_fixtures**
  - Retrieves all fixtures for a given league and season
  - Example: `get_league_fixtures(league_id=39, season=2023)`

- **get_league_schedule_by_date**
  - Retrieves the schedule for a league on specified dates
  - Example: `get_league_schedule_by_date(league_name="Premier League", date=["2024-03-08", "2024-03-09"], season="2023")`

### Player Data

- **get_player_id**
  - Retrieve player IDs and information for players matching a name
  - Example: `get_player_id(player_name="Messi")`

- **get_player_profile**
  - Retrieve a player's profile by their last name
  - Example: `get_player_profile(player_name="Messi")`

- **get_player_statistics**
  - Retrieve detailed player statistics by seasons and league name
  - Example: `get_player_statistics(player_id=154, seasons=[2022, 2023], league_name="La Liga")`

- **get_player_statistics_2**
  - Retrieve detailed player statistics by seasons and league ID
  - Example: `get_player_statistics_2(player_id=154, seasons=[2022, 2023], league_id=140)`

### Team Data

- **get_team_fixtures**
  - Returns past or upcoming fixtures for a team
  - Example: `get_team_fixtures(team_name="Manchester United", type="past", limit=3)`

- **get_team_fixtures_by_date_range**
  - Retrieve fixtures for a team within a date range
  - Example: `get_team_fixtures_by_date_range(team_name="Liverpool", from_date="2023-09-01", to_date="2023-09-30", season="2023")`

- **get_team_info**
  - Retrieve basic information about a specific team
  - Example: `get_team_info(team_name="Real Madrid")`

### Match/Fixture Data

- **get_fixture_statistics**
  - Retrieves detailed statistics for a specific fixture
  - Example: `get_fixture_statistics(fixture_id=867946)`

- **get_fixture_events**
  - Retrieves all in-game events for a fixture (goals, cards, subs)
  - Example: `get_fixture_events(fixture_id=867946)`

- **get_multiple_fixtures_stats**
  - Retrieves statistics for multiple fixtures at once
  - Example: `get_multiple_fixtures_stats(fixture_ids=[867946, 867947, 867948])`

### Live Match Data

- **get_live_match_for_team**
  - Checks if a team is currently playing live
  - Example: `get_live_match_for_team(team_name="Chelsea")`

- **get_live_stats_for_team**
  - Retrieves live in-game stats for a team in a match
  - Example: `get_live_stats_for_team(team_name="Liverpool")`

- **get_live_match_timeline**
  - Retrieves real-time timeline of events for a team's live match
  - Example: `get_live_match_timeline(team_name="Manchester City")`

## Usage

The server is implemented using the Fast MCP framework and can be run as a standalone service.

```python
# Start the server
python soccer_server.py
# or
mcp run soccer-server.py
```

### Configuration

- The server runs with a 30-second timeout for more reliable operation
- Signal handlers are implemented for graceful shutdown (Ctrl+C)

### Usage with Claude Desktop

#### Option 1: Using Docker (Recommended)

1. Clone this repository
```
git clone https://github.com/obinopaul/soccer-mcp-server.git
cd soccer-mcp-server
```

2. Install dependencies
```
pip install -r requirements.txt
```

3. Build the Docker image
```
docker build -t soccer_server .
```

4. Run the Docker container (ensure your API key is passed as an environment variable)
```
docker run -d -p 5000:5000 -e RAPID_API_KEY_FOOTBALL=your_api_key_here --name soccer_server soccer_server
```

5. Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "soccer_server": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "soccer_server",
        "python",
        "soccer_server.py"
      ],
      "env": {
        "RAPID_API_KEY_FOOTBALL": "your_api_key_here"
      }
    }
  }
}
```

#### Option 2: Direct Python Execution

1. Clone this repository
```
git clone https://github.com/obinopaul/soccer-mcp-server.git
cd soccer-mcp-server
```

2. Install dependencies
```
pip install -r requirements.txt
```

3. Set the API key environment variable
```
export RAPID_API_KEY_FOOTBALL=your_api_key_here
```

4. Add this to your `claude_desktop_config.json`, adjusting the Python path as needed:

```json
{
  "mcpServers": {
    "soccer_server": {
      "command": "/path/to/your/python",
      "args": [
        "/path/to/soccer_server.py"
      ],
      "env": {
        "RAPID_API_KEY_FOOTBALL": "your_api_key_here"
      }
    }
  }
}
```

After adding your chosen configuration, restart Claude Desktop to load the soccer server. You'll then be able to use all the football data tools in your conversations with Claude.

## Technical Details

The server is built on:
- API-Football via RapidAPI
- MCP for API interface
- Pydantic for input validation
- Requests for API communication

## License

This MCP server is available under the MIT License.