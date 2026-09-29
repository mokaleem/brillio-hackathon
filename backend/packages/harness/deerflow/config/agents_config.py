"""Configuration and loaders for custom agents.

Custom agents are stored per-user under ``{base_dir}/users/{user_id}/agents/{name}/``.
A legacy shared layout at ``{base_dir}/agents/{name}/`` is still readable so that
installations that pre-date user isolation continue to work until they run the
``scripts/migrate_user_isolation.py`` migration. New writes always target the
per-user layout.
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from deerflow.config.paths import get_paths
from deerflow.runtime.user_context import get_effective_user_id

logger = logging.getLogger(__name__)

SOUL_FILENAME = "SOUL.md"
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


def validate_agent_name(name: str | None) -> str | None:
    """Validate a custom agent name before using it in filesystem paths."""
    if name is None:
        return None
    if not isinstance(name, str):
        raise ValueError("Invalid agent name. Expected a string or None.")
    if not AGENT_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")
    return name


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None
    # skills controls which skills are loaded into the agent's prompt:
    # - None (or omitted): load all enabled skills (default fallback behavior)
    # - [] (explicit empty list): disable all skills
    # - ["skill1", "skill2"]: load only the specified skills
    skills: list[str] | None = None


def _get_registry_agent_descriptor(name: str):
    try:
        from deerflow.internal_registry import ExtensionKind, load_runtime_extension_catalog

        catalog = load_runtime_extension_catalog()
    except Exception:
        logger.exception("Failed to load registry agents")
        return None, None

    for extension in catalog.enabled(kind=ExtensionKind.AGENT):
        if extension.name == name:
            return catalog, extension
    return catalog, None


def _agent_config_from_registry_descriptor(extension) -> AgentConfig:
    metadata = extension.metadata or {}
    config_data = metadata.get("config")
    if not isinstance(config_data, dict):
        config_data = {}

    data: dict[str, Any] = {
        "name": extension.name,
        "description": config_data.get("description", extension.description),
    }
    for field in ("model", "tool_groups", "skills"):
        value = config_data.get(field, metadata.get(field))
        if value is not None:
            data[field] = value
    return AgentConfig(**data)


def _load_registry_agent_config(name: str) -> AgentConfig | None:
    _catalog, extension = _get_registry_agent_descriptor(name)
    if extension is None:
        return None
    from deerflow.internal_registry import ExtensionPermissionError, require_extension_runtime_permission

    try:
        require_extension_runtime_permission(extension)
    except ExtensionPermissionError as exc:
        logger.warning("Registry agent %s blocked by runtime extension policy: %s", name, exc)
        return None
    return _agent_config_from_registry_descriptor(extension)


def _load_registry_agent_soul(name: str) -> str | None:
    catalog, extension = _get_registry_agent_descriptor(name)
    if extension is None:
        return None
    from deerflow.internal_registry import ExtensionPermissionError, require_extension_runtime_permission

    try:
        require_extension_runtime_permission(extension)
    except ExtensionPermissionError as exc:
        logger.warning("Registry agent %s soul blocked by runtime extension policy: %s", name, exc)
        return None

    metadata = extension.metadata or {}
    soul = metadata.get("soul")
    if isinstance(soul, str):
        return soul.strip() or None

    soul_path = metadata.get("soul_path")
    if isinstance(soul_path, str) and catalog is not None:
        root = catalog.repo_root.resolve(strict=False)
        target = (root / soul_path).resolve(strict=False)
        try:
            target.relative_to(root)
        except ValueError:
            logger.warning("Registry agent %s soul_path escapes repository root: %s", name, soul_path)
            return None
        try:
            content = target.read_text(encoding="utf-8").strip()
        except OSError:
            logger.warning("Failed to read registry agent %s soul_path: %s", name, target, exc_info=True)
            return None
        return content or None

    return None


def _list_registry_agent_configs() -> list[AgentConfig]:
    try:
        from deerflow.internal_registry import ExtensionKind, load_runtime_extension_catalog

        catalog = load_runtime_extension_catalog()
    except Exception:
        logger.exception("Failed to list registry agents")
        return []
    agents: list[AgentConfig] = []
    for extension in catalog.enabled(kind=ExtensionKind.AGENT):
        from deerflow.internal_registry import ExtensionPermissionError, require_extension_runtime_permission

        try:
            require_extension_runtime_permission(extension)
        except ExtensionPermissionError as exc:
            logger.warning("Registry agent %s blocked by runtime extension policy: %s", extension.name, exc)
            continue
        agents.append(_agent_config_from_registry_descriptor(extension))
    return agents


def resolve_agent_dir(name: str, *, user_id: str | None = None) -> Path:
    """Return the on-disk directory for an agent, preferring the per-user layout.

    Resolution order:
    1. ``{base_dir}/users/{user_id}/agents/{name}/`` (per-user, current layout).
    2. ``{base_dir}/agents/{name}/`` (legacy shared layout — read-only fallback).

    If neither exists, the per-user path is returned so callers that intend to
    create the agent write into the new layout.

    Args:
        name: Validated agent name.
        user_id: Owner of the agent. Defaults to the effective user from the
            request context (or ``"default"`` in no-auth mode).
    """
    paths = get_paths()
    effective_user = user_id or get_effective_user_id()
    user_path = paths.user_agent_dir(effective_user, name)
    # Require config.yaml to confirm this is a genuine agent directory,
    # not a leftover from memory/storage writes (see #3390).
    if user_path.exists() and (user_path / "config.yaml").exists():
        return user_path

    legacy_path = paths.agent_dir(name)
    if legacy_path.exists() and (legacy_path / "config.yaml").exists():
        return legacy_path

    return user_path


def load_agent_config(name: str | None, *, user_id: str | None = None) -> AgentConfig | None:
    """Load the custom or default agent's config from its directory.

    Reads from the per-user layout first; falls back to the legacy shared layout
    for installations that have not yet been migrated.

    Args:
        name: The agent name.
        user_id: Owner of the agent. Defaults to the effective user from the
            current request context.

    Returns:
        AgentConfig instance, or ``None`` if ``name`` is ``None``.

    Raises:
        FileNotFoundError: If the agent directory or config.yaml does not exist.
        ValueError: If config.yaml cannot be parsed.
    """

    if name is None:
        return None

    name = validate_agent_name(name)
    agent_dir = resolve_agent_dir(name, user_id=user_id)
    config_file = agent_dir / "config.yaml"

    if not agent_dir.exists():
        registry_config = _load_registry_agent_config(name)
        if registry_config is not None:
            return registry_config
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")

    if not config_file.exists():
        registry_config = _load_registry_agent_config(name)
        if registry_config is not None:
            return registry_config
        raise FileNotFoundError(f"Agent config not found: {config_file}")

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse agent config {config_file}: {e}") from e

    # Ensure name is set from directory name if not in file
    if "name" not in data:
        data["name"] = name

    # Strip unknown fields before passing to Pydantic (e.g. legacy prompt_file)
    known_fields = set(AgentConfig.model_fields.keys())
    data = {k: v for k, v in data.items() if k in known_fields}

    return AgentConfig(**data)


def load_agent_soul(agent_name: str | None, *, user_id: str | None = None) -> str | None:
    """Read the SOUL.md file for a custom agent, if it exists.

    SOUL.md defines the agent's personality, values, and behavioral guardrails.
    It is injected into the lead agent's system prompt as additional context.

    Args:
        agent_name: The name of the agent or None for the default agent.
        user_id: Owner of the agent. Defaults to the effective user from the
            current request context.

    Returns:
        The SOUL.md content as a string, or None if the file does not exist.
    """
    if agent_name:
        agent_dir = resolve_agent_dir(agent_name, user_id=user_id)
    else:
        agent_dir = get_paths().base_dir
    soul_path = agent_dir / SOUL_FILENAME
    if not soul_path.exists():
        return _load_registry_agent_soul(agent_name) if agent_name else None
    content = soul_path.read_text(encoding="utf-8").strip()
    if content:
        return content
    return _load_registry_agent_soul(agent_name) if agent_name else None


def list_custom_agents(*, user_id: str | None = None) -> list[AgentConfig]:
    """Scan the agents directory and return all valid custom agents.

    Returns the union of agents in the per-user layout and the legacy shared
    layout, so that pre-migration installations remain visible until they are
    migrated. Per-user entries shadow legacy entries with the same name.

    Args:
        user_id: Owner whose agents to list. Defaults to the effective user
            from the current request context.

    Returns:
        List of AgentConfig for each valid agent directory found.
    """
    paths = get_paths()
    effective_user = user_id or get_effective_user_id()

    seen: set[str] = set()
    agents: list[AgentConfig] = []

    user_root = paths.user_agents_dir(effective_user)
    legacy_root = paths.agents_dir

    for root in (user_root, legacy_root):
        if not root.exists():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name in seen:
                continue
            config_file = entry / "config.yaml"
            if not config_file.exists():
                logger.debug(f"Skipping {entry.name}: no config.yaml")
                continue

            try:
                agent_cfg = load_agent_config(entry.name, user_id=effective_user)
                if agent_cfg is None:
                    continue
                agents.append(agent_cfg)
                seen.add(entry.name)
            except Exception as e:
                logger.warning(f"Skipping agent '{entry.name}': {e}")

    for agent_cfg in _list_registry_agent_configs():
        if agent_cfg.name in seen:
            continue
        agents.append(agent_cfg)
        seen.add(agent_cfg.name)

    agents.sort(key=lambda a: a.name)
    return agents
