# Internal MCP Servers

Place local MCP server definitions, wrappers, or documentation here. Runtime MCP server configuration should be referenced from registry manifests or `extensions_config.json`, not hard-coded in the harness.

Registry-backed MCP descriptors use the same shape as `extensions_config.json`
server entries inside descriptor `metadata`. Keep demo descriptors disabled
until the backing MCP server module is implemented, then flip `enabled` in the
registry or override it from `extensions_config.json`.
