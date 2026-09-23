from scripts.check_scenario import main


def test_main_passes_without_api_key(monkeypatch):
    monkeypatch.setenv("AKIM_NO_LLM", "1")
    assert main() == 0
