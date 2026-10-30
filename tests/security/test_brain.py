import pytest

from phantomshell.brain import OllamaBrain


def test_brain_refuses_non_loopback_model_urls() -> None:
    for url in ("https://example.com", "http://localhost:11434", "http://127.0.0.1.evil:11434", "http://user@127.0.0.1:11434"):
        with pytest.raises(ValueError):
            OllamaBrain(base_url=url)
