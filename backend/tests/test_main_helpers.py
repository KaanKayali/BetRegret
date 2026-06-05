import pytest

import main

def test_extract_used_tools_reads_footer():
    text = "Analyse\nUsed Tools: [get_team_info, predict_match_outcome]"

    assert main._extract_used_tools(text) == ["get_team_info", "predict_match_outcome"]


def test_extract_used_tools_returns_empty_list_without_footer():
    assert main._extract_used_tools("Analyse ohne Footer") == []


class _FakeGuard:
    def __init__(self, decision):
        self.decision = decision
        self.seen_prompt = None

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, prompt):
        self.seen_prompt = prompt
        return main.GuardDecision(**self.decision)


@pytest.mark.asyncio
async def test_run_guard_uses_structured_output(monkeypatch):
    fake_guard = _FakeGuard({"allowed": False, "message": "Nur Fussballthemen sind erlaubt."})
    monkeypatch.setattr(main, "guard", fake_guard)

    result = await main._run_guard("Das Wetter ist heute schön.")

    assert result.allowed is False
    assert "Fussball" in result.message
    assert "Text:" in fake_guard.seen_prompt
