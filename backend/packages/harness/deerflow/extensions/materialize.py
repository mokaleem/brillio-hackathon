from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain.tools import BaseTool

from deerflow.audit import record_extension_execution
from deerflow.config.extensions_config import McpServerConfig
from deerflow.config.tool_config import ToolConfig
from deerflow.extensions.descriptors import ExtensionDescriptor, ExtensionKind
from deerflow.extensions.entrypoints import resolve_python_entrypoint
from deerflow.extensions.policy import require_extension_runtime_permission
from deerflow.reflection import resolve_variable


def materialize_tool(extension: ExtensionDescriptor) -> BaseTool:
    _require_kind(extension, ExtensionKind.TOOL)
    require_extension_runtime_permission(extension)
    if not extension.entrypoint:
        raise ValueError(f"Tool extension '{extension.name}' must define an entrypoint.")

    resolved = resolve_variable(extension.entrypoint)
    if isinstance(resolved, BaseTool):
        return _with_tool_audit(resolved, extension)
    if callable(resolved):
        created = resolved()
        if isinstance(created, BaseTool):
            return _with_tool_audit(created, extension)
    raise TypeError(f"Tool extension '{extension.name}' did not resolve to a BaseTool or zero-argument BaseTool factory.")


def materialize_tool_config(extension: ExtensionDescriptor, *, default_group: str = "registry") -> ToolConfig:
    _require_kind(extension, ExtensionKind.TOOL)
    require_extension_runtime_permission(extension)
    if not extension.entrypoint:
        raise ValueError(f"Tool extension '{extension.name}' must define an entrypoint.")
    group = extension.metadata.get("group") or extension.category or default_group
    return ToolConfig(name=extension.name, group=str(group), use=extension.entrypoint)


def materialize_mcp_server_config(extension: ExtensionDescriptor) -> McpServerConfig:
    _require_kind(extension, ExtensionKind.MCP)
    require_extension_runtime_permission(extension)
    payload = dict(extension.metadata)
    payload.setdefault("enabled", extension.enabled)
    payload.setdefault("description", extension.description)
    return McpServerConfig.model_validate(payload)


def materialize_skill_path(extension: ExtensionDescriptor, *, repo_root: Path | str) -> Path:
    _require_kind(extension, ExtensionKind.SKILL)
    require_extension_runtime_permission(extension)
    if not extension.entrypoint:
        raise ValueError(f"Skill extension '{extension.name}' must define an entrypoint path.")
    root = Path(repo_root).resolve(strict=False)
    target = (root / extension.entrypoint).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Skill extension '{extension.name}' must resolve within the repository.") from exc
    return target


def materialize_agent_factory(extension: ExtensionDescriptor) -> Callable[..., Any]:
    _require_kind(extension, ExtensionKind.AGENT)
    require_extension_runtime_permission(extension)
    if not extension.entrypoint:
        raise ValueError(f"Agent extension '{extension.name}' must define an entrypoint.")
    return resolve_python_entrypoint(extension.entrypoint)


def _require_kind(extension: ExtensionDescriptor, expected: ExtensionKind) -> None:
    if extension.kind is not expected:
        raise ValueError(f"Expected {expected.value} extension, got {extension.kind.value}.")


def _with_tool_audit(tool: BaseTool, extension: ExtensionDescriptor) -> BaseTool:
    if getattr(tool, "_deerflow_audit_wrapped", False):
        object.__setattr__(tool, "_deerflow_audit_extension", extension)
        return tool

    original_invoke = tool.invoke
    object.__setattr__(tool, "_deerflow_audit_original_invoke", original_invoke)
    object.__setattr__(tool, "_deerflow_audit_extension", extension)

    def audited_invoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        started_at = datetime.now(UTC)
        current_extension = getattr(tool, "_deerflow_audit_extension", extension)
        try:
            output = original_invoke(input, config=config, **kwargs)
        except BaseException as exc:
            record_extension_execution(
                current_extension,
                input_value=input,
                status="error",
                started_at=started_at,
                error=exc,
            )
            raise
        record_extension_execution(
            current_extension,
            input_value=input,
            output_value=output,
            status="success",
            started_at=started_at,
        )
        return output

    object.__setattr__(tool, "invoke", audited_invoke)
    object.__setattr__(tool, "_deerflow_audit_wrapped", True)
    return tool
