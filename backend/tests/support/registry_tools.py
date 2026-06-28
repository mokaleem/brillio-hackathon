from langchain_core.tools import tool


@tool
def company_metric_tool(metric: str) -> str:
    """Look up an internal company metric by name."""
    return f"metric:{metric}"


@tool
def company_export_tool(name: str) -> str:
    """Export an internal company artifact by name."""
    return f"export:{name}"
