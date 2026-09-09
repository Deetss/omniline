"""Exercises install -> backup -> uninstall -> restore for every harness
against a fake $HOME (OMNILINE_TEST_HOME), so this never touches a
real Claude Code / antigravity-cli / Codex config.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from omniline import installer  # noqa: E402


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNILINE_TEST_HOME", str(tmp_path))
    return tmp_path


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# --- Claude Code -------------------------------------------------------------

def test_claude_code_install_backup_uninstall_restore(fake_home):
    settings_path = installer._claude_settings_path()
    original = {"otherSetting": "keep-me", "statusLine": {"type": "command", "command": "old-script"}}
    _write_json(settings_path, original)

    target = "/repo/bin/claude-statusline"
    installer.install_claude_code(target)

    with open(settings_path) as f:
        after_install = json.load(f)
    assert after_install["statusLine"] == {"type": "command", "command": target}
    assert after_install["otherSetting"] == "keep-me", "unrelated settings must survive"

    pre_install_backups = installer.list_backups("claude_code")
    assert len(pre_install_backups) == 1
    with open(pre_install_backups[0]) as f:
        assert json.load(f) == original, "backup must be byte-for-byte the pre-install state"

    installer.uninstall_claude_code()
    with open(settings_path) as f:
        after_uninstall = json.load(f)
    assert "statusLine" not in after_uninstall
    assert after_uninstall["otherSetting"] == "keep-me"

    backups_after_uninstall = installer.list_backups("claude_code")
    assert len(backups_after_uninstall) == 2, "uninstall must also back up what it removes"

    # Restore the ORIGINAL pre-install backup (oldest = last in newest-first list)
    original_backup = sorted(backups_after_uninstall)[0]
    installer.restore_backup("claude_code", settings_path, original_backup)
    with open(settings_path) as f:
        restored = json.load(f)
    assert restored == original, "restore must bring back exactly the pre-install content"

    # restoring itself must not be silently destructive: it backs up first
    assert len(installer.list_backups("claude_code")) == 3


def test_claude_code_install_from_nothing(fake_home):
    settings_path = installer._claude_settings_path()
    assert not os.path.isfile(settings_path)

    installer.install_claude_code("/repo/bin/claude-statusline")

    assert os.path.isfile(settings_path)
    assert installer.list_backups("claude_code") == [], "nothing existed, so nothing to back up"


def test_claude_code_uninstall_when_nothing_configured(fake_home, capsys):
    _write_json(installer._claude_settings_path(), {"unrelated": True})
    installer.uninstall_claude_code()
    out = capsys.readouterr().out
    assert "nothing to remove" in out
    assert installer.list_backups("claude_code") == []


# --- antigravity-cli ----------------------------------------------------------

def test_antigravity_install_backup_uninstall_restore(fake_home):
    settings_path = installer._antigravity_settings_path()
    original = {"statusLine": {"type": "command", "command": "stale-path", "enabled": True}}
    _write_json(settings_path, original)

    target = "/repo/bin/antigravity-statusline"
    installer.install_antigravity(target)

    with open(settings_path) as f:
        after_install = json.load(f)
    assert after_install["statusLine"]["command"] == target
    assert after_install["statusLine"]["enabled"] is True

    installer.uninstall_antigravity()
    with open(settings_path) as f:
        assert "statusLine" not in json.load(f)

    backups = installer.list_backups("antigravity")
    assert len(backups) == 2
    original_backup = sorted(backups)[0]
    installer.restore_backup("antigravity", settings_path, original_backup)
    with open(settings_path) as f:
        assert json.load(f) == original


def test_backups_for_different_harnesses_dont_collide(fake_home):
    """Both settings files are literally named settings.json -- the label
    prefix is what keeps their backups distinguishable."""
    _write_json(installer._claude_settings_path(), {"statusLine": {"type": "command", "command": "a"}})
    _write_json(installer._antigravity_settings_path(), {"statusLine": {"type": "command", "command": "b"}})

    installer.install_claude_code("/repo/bin/claude-statusline")
    installer.install_antigravity("/repo/bin/antigravity-statusline")

    claude_backups = installer.list_backups("claude_code")
    antigravity_backups = installer.list_backups("antigravity")
    assert len(claude_backups) == 1
    assert len(antigravity_backups) == 1
    assert claude_backups[0] != antigravity_backups[0]
    with open(claude_backups[0]) as f:
        assert json.load(f)["statusLine"]["command"] == "a"
    with open(antigravity_backups[0]) as f:
        assert json.load(f)["statusLine"]["command"] == "b"


# --- Codex ---------------------------------------------------------------------

CODEX_ORIGINAL = """model = "gpt-5-mini"

[model_providers.azure-foundry]
name = "Azure AI Foundry"

[[models]]
id = "gpt-5-mini"
"""


def test_codex_install_backup_uninstall_restore_no_existing_tui(fake_home):
    config_path = installer._codex_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        f.write(CODEX_ORIGINAL)

    installer.install_codex(["current-dir", "git-branch"])

    text = open(config_path).read()
    assert '[tui]' in text
    assert 'status_line = ["current-dir", "git-branch"]' in text
    # Unrelated sections must be untouched
    assert "[model_providers.azure-foundry]" in text
    assert '[[models]]' in text

    backups = installer.list_backups("codex")
    assert len(backups) == 1
    assert open(backups[0]).read() == CODEX_ORIGINAL

    installer.uninstall_codex()
    after_uninstall = open(config_path).read()
    assert "status_line" not in after_uninstall
    assert "[model_providers.azure-foundry]" in after_uninstall

    backups = installer.list_backups("codex")
    assert len(backups) == 2
    original_backup = sorted(backups)[0]
    installer.restore_backup("codex", config_path, original_backup)
    assert open(config_path).read() == CODEX_ORIGINAL


def test_codex_install_replaces_existing_status_line(fake_home):
    config_path = installer._codex_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    original = 'model = "gpt-5-mini"\n\n[tui]\nstatus_line = ["model"]\n'
    with open(config_path, "w") as f:
        f.write(original)

    installer.install_codex(["current-dir", "context-used"])

    text = open(config_path).read()
    assert 'status_line = ["current-dir", "context-used"]' in text
    assert 'status_line = ["model"]' not in text
    assert open(installer.list_backups("codex")[0]).read() == original


def test_codex_install_rejects_unknown_items(fake_home, capsys):
    config_path = installer._codex_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        f.write("model = \"gpt-5-mini\"\n")

    installer.install_codex(["current-dir", "not-a-real-item"])

    out = capsys.readouterr().out
    assert "unrecognized item id(s)" in out
    text = open(config_path).read()
    assert 'status_line = ["current-dir"]' in text
    assert "not-a-real-item" not in text
