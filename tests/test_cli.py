from typer.testing import CliRunner
from url_resolver.cli import app

runner = CliRunner()

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "url-resolver" in result.output.lower() or "usage" in result.output.lower()

def test_parse_command_extract_only():
    result = runner.invoke(app, ["parse", "https://ouo.io/test123", "--extract-only"])
    assert result.exit_code == 0

def test_parse_command_json_output():
    result = runner.invoke(app, ["parse", "https://ouo.io/test123", "--extract-only", "--json"])
    assert result.exit_code == 0
    assert "direct_url" in result.output
    assert "tags" in result.output
    assert "models" in result.output
