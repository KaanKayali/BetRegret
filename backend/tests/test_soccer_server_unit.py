import soccer_server


def test_normalize_string_strips_accents_and_clubs():
    assert soccer_server._normalize_string("FC Bayern München") == "bayern munchen"


def test_score_team_match_prefers_exact_tla():
    team = {"name": "Manchester City", "shortName": "Man City", "tla": "MCI"}
    query = soccer_server._normalize_string("MCI")

    assert soccer_server._score_team_match(team, query) > soccer_server._score_team_match(team, soccer_server._normalize_string("manchester"))


def test_extract_match_score_uses_fulltime_first():
    match = {
        "score": {
            "fullTime": {"home": 2, "away": 1},
            "regularTime": {"home": 1, "away": 1},
        }
    }

    assert soccer_server._extract_match_score(match) == (2, 1)


def test_extract_match_score_falls_back_to_regular_time():
    match = {
        "score": {
            "fullTime": {"home": None, "away": None},
            "regularTime": {"home": 0, "away": 0},
        }
    }

    assert soccer_server._extract_match_score(match) == (0, 0)


def test_extract_match_score_returns_none_when_no_score_exists():
    assert soccer_server._extract_match_score({"score": {}}) == (None, None)
