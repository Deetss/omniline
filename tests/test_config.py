"""Exercises the config module's loading (missing/malformed files must
degrade to defaults, never crash a statusline render) and template
rendering (token substitution, and the empty-token/separator-collapsing
rule that keeps a template's own literal text tidy when a segment has
nothing to show).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from omniline import config  # noqa: E402


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNILINE_TEST_HOME", str(tmp_path))
    return tmp_path


def _write_config(home, text):
    path = os.path.join(home, ".config", "omniline", "config.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


# --- load() -------------------------------------------------------------

def test_load_missing_file_returns_empty(fake_home):
    assert config.load() == {}


def test_load_malformed_json_returns_empty(fake_home):
    _write_config(fake_home, "{ not valid json")
    assert config.load() == {}


def test_load_non_dict_json_returns_empty(fake_home):
    _write_config(fake_home, "[1, 2, 3]")
    assert config.load() == {}


def test_load_valid_config(fake_home):
    _write_config(fake_home, '{"claude_code": {"segments": ["model"]}}')
    assert config.load() == {"claude_code": {"segments": ["model"]}}


# --- harness_section / segment_style / style_str / style_num ------------

def test_harness_section_missing_key_returns_empty():
    assert config.harness_section({}, "claude_code") == {}


def test_harness_section_non_dict_value_returns_empty():
    assert config.harness_section({"claude_code": "oops"}, "claude_code") == {}


def test_segment_style_missing_returns_empty():
    assert config.segment_style({}, "context") == {}
    assert config.segment_style({"style": "oops"}, "context") == {}
    assert config.segment_style({"style": {}}, "context") == {}


def test_style_str_falls_back_on_missing_or_wrong_type():
    assert config.style_str({}, "label", "ctx") == "ctx"
    assert config.style_str({"label": 5}, "label", "ctx") == "ctx"
    assert config.style_str({"label": "context"}, "label", "ctx") == "context"


def test_style_num_falls_back_on_missing_or_wrong_type():
    assert config.style_num({}, "warn_pct", 50) == 50
    assert config.style_num({"warn_pct": "high"}, "warn_pct", 50) == 50
    assert config.style_num({"warn_pct": True}, "warn_pct", 50) == 50
    assert config.style_num({"warn_pct": 60}, "warn_pct", 50) == 60
    assert config.style_num({"warn_pct": "60"}, "warn_pct", 50) == 60


# --- resolve_template -----------------------------------------------------

def test_resolve_template_prefers_explicit_template():
    section = {"template": "$model only", "segments": ["account"]}
    assert config.resolve_template(section, ["account"]) == "$model only"


def test_resolve_template_uses_segments_list_and_separator():
    section = {"segments": ["model", "path"], "separator": " | "}
    result = config.resolve_template(section, ["account", "path", "model"])
    assert result == f"$model{config.DIM} | {config.RESET}$path"


def test_resolve_template_falls_back_to_default_order():
    result = config.resolve_template({}, ["account", "path"])
    assert result == f"$account{config.DIM} · {config.RESET}$path"


# --- render_template -------------------------------------------------------

def test_render_template_basic_substitution():
    result = config.render_template("$a-$b", {"a": "X", "b": "Y"})
    assert result == "X-Y"


def test_render_template_drops_empty_token_and_its_leading_literal():
    result = config.render_template("$a · $b", {"a": "", "b": "Y"})
    assert result == "Y"


def test_render_template_drops_trailing_empty_token_and_separator():
    result = config.render_template("$a · $b", {"a": "X", "b": ""})
    assert result == "X"


def test_render_template_unknown_token_treated_as_empty():
    result = config.render_template("$a · $nope", {"a": "X"})
    assert result == "X"


def test_render_template_keeps_trailing_literal_text():
    result = config.render_template("$a!", {"a": "X"})
    assert result == "X!"


def test_render_template_no_tokens_returns_literal():
    assert config.render_template("just text", {}) == "just text"


def test_render_template_all_empty_returns_empty_string():
    assert config.render_template("$a · $b", {}) == ""
