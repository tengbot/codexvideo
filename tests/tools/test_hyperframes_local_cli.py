from pathlib import Path

import pytest

from tools.video.hyperframes_compose import HyperFramesCompose


def test_explicit_cached_cli_runs_without_npx(monkeypatch, tmp_path):
    entry = tmp_path / "cli.js"
    entry.write_text("// local fixture\n")
    monkeypatch.setenv("CODEXVIDEO_HYPERFRAMES_CLI", str(entry))
    command = HyperFramesCompose._cli_command()
    assert Path(command[0]).name in {"node", "node.exe"}
    assert command[1:] == [str(entry)]


def test_missing_explicit_cli_does_not_fall_back_to_install(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEXVIDEO_HYPERFRAMES_CLI", str(tmp_path / "missing.js"))
    with pytest.raises(OSError, match="does not exist"):
        HyperFramesCompose._cli_command()


def test_default_command_never_installs(monkeypatch):
    monkeypatch.delenv("CODEXVIDEO_HYPERFRAMES_CLI", raising=False)
    assert HyperFramesCompose._cli_command()[1:] == ["--no-install", "hyperframes@0.8.29"]
