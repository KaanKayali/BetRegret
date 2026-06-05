import soccer_server


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_build_recent_form_uses_recent_finished_matches(monkeypatch):
    matches = [
        {
            "utcDate": "2026-04-01T18:00:00Z",
            "homeTeam": {"id": 3, "name": "Opponent Away"},
            "awayTeam": {"id": 1, "name": "Test FC"},
            "score": {"fullTime": {"home": 1, "away": 1}},
        },
        {
            "utcDate": "2026-05-01T18:00:00Z",
            "homeTeam": {"id": 1, "name": "Test FC"},
            "awayTeam": {"id": 2, "name": "Opponent Home"},
            "score": {"fullTime": {"home": 2, "away": 0}},
        },
    ]

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse({"matches": matches})

    monkeypatch.setattr(soccer_server.requests, "get", fake_get)

    result = soccer_server._build_recent_form(
        "Test FC",
        headers={"X-Auth-Token": "token"},
        base_url="https://api.football-data.org/v4",
        team={"id": 1, "name": "Test FC"},
        limit=2,
    )

    assert result["matches_considered"] == 2
    assert result["points_per_game"] == 2.0
    assert result["home_points_per_game"] == 3.0
    assert result["away_points_per_game"] == 1.0
    assert result["last_results"] == "WD"


def test_predict_match_outcome_uses_mocked_table_data(monkeypatch):
    def fake_team_stats(team_name, headers, base_url, team=None):
        if "Home" in team_name:
            return {
                "team_name": "Home United",
                "team_id": 1,
                "position": 1,
                "playedGames": 10,
                "points": 24,
                "goalsFor": 20,
                "goalsAgainst": 8,
                "goalDifference": 12,
                "league_name": "Test League",
            }

        return {
            "team_name": "Away City",
            "team_id": 2,
            "position": 12,
            "playedGames": 10,
            "points": 9,
            "goalsFor": 10,
            "goalsAgainst": 18,
            "goalDifference": -8,
            "league_name": "Test League",
        }

    monkeypatch.setattr(soccer_server, "_get_team_standings_data", fake_team_stats)

    result = soccer_server.predict_match_outcome("Home United", "Away City")
    prediction = result["prediction"]

    assert prediction["home_team"] == "Home United"
    assert prediction["away_team"] == "Away City"
    assert prediction["recommendation"] == "Home Win"
    assert prediction["analysis"]["home_league"] == "Test League"
    assert prediction["analysis"]["away_league"] == "Test League"

    home_win = float(prediction["probabilities"]["home_win"].rstrip("%"))
    draw = float(prediction["probabilities"]["draw"].rstrip("%"))
    away_win = float(prediction["probabilities"]["away_win"].rstrip("%"))

    assert round(home_win + draw + away_win, 1) == 100.0
    assert prediction["expected_score"].count("-") == 1


def test_fetch_json_rate_limit_retry(monkeypatch):
    """
    Test that _fetch_json retries successfully when encountering a 429 rate limit.
    """
    import requests

    calls = 0

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(response=self)

        def json(self):
            return self._json_data

    def mock_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return MockResponse(429, {})
        return MockResponse(200, {"teams": [{"id": 1, "name": "Arsenal FC"}]})

    monkeypatch.setattr(soccer_server.time, "sleep", lambda x: None)
    monkeypatch.setattr(soccer_server.REQUEST_SESSION, "get", mock_get)

    headers = {"X-Auth-Token": "test"}
    res = soccer_server._fetch_json("https://api.fake.com", headers)
    
    assert res == {"teams": [{"id": 1, "name": "Arsenal FC"}]}
    assert calls == 2


def test_predict_match_outcome_zero_games_played(monkeypatch):
    """
    Test that predict_match_outcome handles teams with zero games played (new season)
    without raising a division by zero error.
    """
    def fake_zero_games_stats(team_name, headers, base_url, team=None):
        return {
            "team_name": team_name,
            "team_id": 1,
            "position": 1,
            "playedGames": 0,
            "points": 0,
            "goalsFor": 0,
            "goalsAgainst": 0,
            "goalDifference": 0,
            "league_name": "Test League",
        }

    monkeypatch.setattr(soccer_server, "_get_team_standings_data", fake_zero_games_stats)
    
    result = soccer_server.predict_match_outcome("Team A", "Team B")
    assert "prediction" in result
    assert result["prediction"]["expected_score"] == "1-1"


