"""Cache for MCP tools to avoid repeated loading."""

import asyncio
import logging
import os
from pathlib import Path

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

_mcp_tools_cache: list[BaseTool] | None = None
_cache_initialized = False
_initialization_lock = asyncio.Lock()
_ConfigSignature = tuple[tuple[str, float | None], ...]
_config_signature: _ConfigSignature | None = None


def _get_config_signature() -> _ConfigSignature:
    """Get the modification signature for MCP config inputs.

    Returns:
        Stable path/mtime pairs for the extensions config and registry manifests.
    """
    from deerflow.config.extensions_config import ExtensionsConfig
    from deerflow.extensions import get_runtime_extension_manifest_paths

    paths: list[Path] = []
    config_path = ExtensionsConfig.resolve_config_path()
    if config_path is not None:
        paths.append(config_path)
    paths.extend(get_runtime_extension_manifest_paths())

    signature: list[tuple[str, float | None]] = []
    for path in paths:
        resolved = path.resolve(strict=False)
        mtime = os.path.getmtime(resolved) if resolved.exists() else None
        signature.append((str(resolved), mtime))
    return tuple(signature)


def _is_cache_stale() -> bool:
    """Check if the cache is stale due to config input changes.

    Returns:
        True if the cache should be invalidated, False otherwise.
    """
    global _config_signature

    if not _cache_initialized:
        return False  # Not initialized yet, not stale

    current_signature = _get_config_signature()

    if _config_signature != current_signature:
        logger.info(
            "MCP config inputs have changed (signature: %s -> %s), cache is stale",
            _config_signature,
            current_signature,
        )
        return True

    return False


async def initialize_mcp_tools() -> list[BaseTool]:
    """Initialize and cache MCP tools.

    This should be called once at application startup.

    Returns:
        List of LangChain tools from all enabled MCP servers.
    """
    global _mcp_tools_cache, _cache_initialized, _config_signature

    async with _initialization_lock:
        if _cache_initialized:
            logger.info("MCP tools already initialized")
            return _mcp_tools_cache or []

        from deerflow.mcp.tools import get_mcp_tools

        logger.info("Initializing MCP tools...")
        _mcp_tools_cache = await get_mcp_tools()
        _cache_initialized = True
        _config_signature = _get_config_signature()
        logger.info(
            "MCP tools initialized: %s tool(s) loaded (config signature: %s)",
            len(_mcp_tools_cache),
            _config_signature,
        )

        return _mcp_tools_cache


def get_cached_mcp_tools() -> list[BaseTool]:
    """Get cached MCP tools with lazy initialization.

    If tools are not initialized, automatically initializes them.
    This ensures MCP tools work in both FastAPI and LangGraph Studio contexts.

    Also checks if the config file has been modified since last initialization,
    and re-initializes if needed. This ensures that changes made through the
    Gateway API are reflected in the Gateway-embedded LangGraph runtime.

    Returns:
        List of cached MCP tools.
    """
    global _cache_initialized

    # Check if cache is stale due to config file changes
    if _is_cache_stale():
        logger.info("MCP cache is stale, resetting for re-initialization...")
        reset_mcp_tools_cache()

    if not _cache_initialized:
        logger.info("MCP tools not initialized, performing lazy initialization...")
        try:
            # Try to initialize in the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running (e.g., in LangGraph Studio),
                # we need to create a new loop in a thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, initialize_mcp_tools())
                    future.result()
            else:
                # If no loop is running, we can use the current loop
                loop.run_until_complete(initialize_mcp_tools())
        except RuntimeError:
            # No event loop exists, create one
            try:
                asyncio.run(initialize_mcp_tools())
            except Exception:
                logger.exception("Failed to lazy-initialize MCP tools")
                return []
        except Exception:
            logger.exception("Failed to lazy-initialize MCP tools")
            return []

    return _mcp_tools_cache or []


def reset_mcp_tools_cache() -> None:
    """Reset the MCP tools cache.

    This is useful for testing or when you want to reload MCP tools.
    Also closes all persistent MCP sessions so they are recreated on
    the next tool load.
    """
    global _mcp_tools_cache, _cache_initialized, _config_signature
    _mcp_tools_cache = None
    _cache_initialized = False
    _config_signature = None

    # Close persistent sessions – they will be recreated by the next
    # get_mcp_tools() call with the (possibly updated) connection config.
    #
    # close_all_sync() already picks the correct strategy per owning loop:
    #   * sessions owned by the *current* running loop are only *signalled*
    #     (their owner task runs __aexit__ once the loop regains control –
    #     this is correct and leak-free, since the loop keeps the task alive),
    #   * sessions on other threads' loops are torn down deterministically,
    #   * idle/closed loops are handled or skipped.
    # We deliberately do NOT try to synchronously wait for the current running
    # loop to finish teardown here: that is a self-deadlock (the loop can only
    # run the teardown after this synchronous call returns control to it).
    try:
        from deerflow.mcp.session_pool import get_session_pool

        get_session_pool().close_all_sync()
    except Exception:
        logger.debug("Could not close MCP session pool on cache reset", exc_info=True)

    from deerflow.mcp.session_pool import reset_session_pool

    reset_session_pool()
    logger.info("MCP tools cache reset")
