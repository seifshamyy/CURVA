import json
import structlog
from curva_agent.observability.logging import configure_logging, get_logger


def test_configure_logging_sets_json_renderer(capsys):
    configure_logging("INFO")
    log = get_logger("test")
    log.info("hello", session_id="20100", tool="search_products")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["session_id"] == "20100"
    assert parsed["tool"] == "search_products"
    assert parsed["level"] == "info"


def test_get_logger_returns_bound_logger():
    log = get_logger("test").bind(session_id="abc")
    assert hasattr(log, "info")