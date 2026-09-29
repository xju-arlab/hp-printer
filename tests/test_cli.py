from typer.testing import CliRunner

from hp_printer import __version__
from hp_printer.cli import app


def test_version_without_subcommand():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_is_offline():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
