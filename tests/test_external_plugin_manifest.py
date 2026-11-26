"""Hermetic tests for external plugin manifests and registry URLs.

Covers three follow-ups:
- ``select`` config params keep their ``options`` array when parsed.
- The official registry/archive URLs point at the website's ``/api`` paths.
- The list-API config dict shape includes ``options``.
"""

from pathlib import Path

from cachibot.services.external_plugins import (
    ARCHIVE_URL,
    FALLBACK_ARCHIVE_URL,
    FALLBACK_REGISTRY_URL,
    REGISTRY_URL,
    _parse_manifest,
)

MANIFEST_TOML = """
[plugin]
name = "image_studio"
display_name = "Image Studio"
version = "1.0.0"
author = "CachiBot"

[[plugin.config]]
name = "defaultSize"
display_name = "Default size"
type = "select"
default = "1024x1024"
description = "Default generated image size"
options = ["1024x1024", "1792x1024", "1024x1792"]

[[plugin.config]]
name = "apiKey"
display_name = "API key"
type = "secret"
default = ""
description = "Provider API key"
"""


def _write_manifest(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / "image_studio"
    plugin_dir.mkdir()
    toml_path = plugin_dir / "plugin.toml"
    toml_path.write_text(MANIFEST_TOML)
    return toml_path


def test_parse_manifest_keeps_select_options(tmp_path):
    manifest = _parse_manifest(_write_manifest(tmp_path))

    select_param = next(p for p in manifest.config if p.name == "defaultSize")
    assert select_param.type == "select"
    assert select_param.options == ["1024x1024", "1792x1024", "1024x1792"]

    text_param = next(p for p in manifest.config if p.name == "apiKey")
    assert text_param.options == []


def test_registry_urls_use_api_prefix():
    assert REGISTRY_URL == "https://cachibot.ai/api/plugins/registry"
    assert ARCHIVE_URL == "https://cachibot.ai/api/plugins/{name}/archive"


def test_fallback_urls_unchanged():
    assert FALLBACK_REGISTRY_URL == (
        "https://raw.githubusercontent.com/jhd3197/CachiBot-Plugins/main/registry.json"
    )
    assert FALLBACK_ARCHIVE_URL == (
        "https://raw.githubusercontent.com/jhd3197/CachiBot-Plugins/main/plugins/{name}"
    )


def test_list_api_config_dict_includes_options(tmp_path):
    """Mirror the config dict built by the external-plugins list route."""
    manifest = _parse_manifest(_write_manifest(tmp_path))
    config = [
        {
            "name": p.name,
            "displayName": p.display_name,
            "type": p.type,
            "default": p.default,
            "description": p.description,
            "options": p.options,
        }
        for p in manifest.config
    ]

    select_entry = next(c for c in config if c["name"] == "defaultSize")
    assert select_entry["options"] == ["1024x1024", "1792x1024", "1024x1792"]

    text_entry = next(c for c in config if c["name"] == "apiKey")
    assert text_entry["options"] == []
