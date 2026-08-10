#!/usr/bin/env python3
"""Read opencli's OWN published command metadata.

`opencli <site> --help -f yaml` emits, per command: name, access (read|write),
aliases, columns, options. That `access:` field is the authority this skill
uses to decide whether a command was a read. A list WE maintain would go stale
the day a new command ships, and nothing would report the staleness.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import yaml


class MetadataUnavailable(Exception):
    """The tool did not tell us; the caller must fail closed."""


def _help_yaml(site, cache_dir, allow_fetch, timeout=60):
    if cache_dir is not None:
        cached = pathlib.Path(cache_dir) / f"{site}.yaml"
        if cached.is_file():
            return cached.read_text(encoding="utf-8")
    if not allow_fetch:
        raise MetadataUnavailable(
            f"no cached metadata for {site!r} and fetching is disabled")
    binary = shutil.which("opencli")
    if binary is None:
        raise MetadataUnavailable("opencli is not on PATH")
    try:
        proc = subprocess.run([binary, site, "--help", "-f", "yaml"],
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise MetadataUnavailable(str(exc)) from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise MetadataUnavailable(
            f"`opencli {site} --help -f yaml` exited {proc.returncode}")
    return proc.stdout


def load_site_metadata(site, cache_dir=None, allow_fetch=True):
    """{command-or-alias: {"name": canonical, "access": "read"|"write"|None}}."""
    text = _help_yaml(site, cache_dir, allow_fetch)
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise MetadataUnavailable(f"{site}: help yaml did not parse: {exc}") from exc
    table = {}
    for command in doc.get("commands") or []:
        if not isinstance(command, dict):
            continue
        name = command.get("name")
        if not name:
            continue
        entry = {"name": name, "access": command.get("access")}
        table[name] = entry
        for alias in command.get("aliases") or []:
            table[alias] = entry
    if not table:
        raise MetadataUnavailable(f"{site}: help yaml listed no commands")
    return table


def access_for(site, command, cache_dir=None, allow_fetch=True):
    """"read" | "write" | None. None means the tool did not tell us."""
    try:
        table = load_site_metadata(site, cache_dir, allow_fetch)
    except MetadataUnavailable:
        return None
    entry = table.get(command)
    if entry is None:
        return None
    access = entry.get("access")
    return access if access in ("read", "write") else None
