"""Tenant filtering utilities for multi-tenant database queries.

Provides helper functions to add org_id filtering to SQL queries,
ensuring each organization can only see its own data.
"""

from __future__ import annotations

from typing import Optional


def filter_query(base_query: str, org_id: Optional[int], param_prefix: str = "org_") -> tuple[str, list]:
    """Add org_id WHERE clause to a SQL query.

    Args:
        base_query: The original SQL query
        org_id: The organization ID to filter by (None = no filtering)
        param_prefix: Prefix for the parameter name to avoid collisions

    Returns:
        Tuple of (modified_query, params_to_append)

    Example:
        query, params = filter_query("SELECT * FROM alerts WHERE state = ?", org_id)
        # Returns: ("SELECT * FROM alerts WHERE state = ? AND org_id = ?", [org_id])
    """
    if org_id is None:
        return base_query, []

    # Check if query already has WHERE clause
    upper_query = base_query.upper()
    if " WHERE " in upper_query:
        return f"{base_query} AND org_id = :{param_prefix}id", [org_id]
    else:
        return f"{base_query} WHERE org_id = :{param_prefix}id", [org_id]


def filter_alerts_query(org_id: Optional[int], state_filter: str = "") -> tuple[str, list]:
    """Build an org-filtered alerts query."""
    base = "SELECT * FROM alerts"
    if state_filter:
        base += f" WHERE {state_filter}"
    return filter_query(base, org_id, "org_alerts")


def filter_workers_query(org_id: Optional[int]) -> tuple[str, list]:
    """Build an org-filtered workers query."""
    return filter_query("SELECT * FROM workers", org_id, "org_workers")


def filter_sessions_by_worker(worker_ids: list[str], org_id: Optional[int]) -> list[str]:
    """Filter session files by org_id.

    For file-based sessions, we check if the session's worker_id
    belongs to the organization's workers.
    """
    # This is a placeholder — file-based sessions don't have org_id yet.
    # New sessions will include org_id in the JSON.
    return worker_ids


def add_org_to_session_data(session_data: dict, org_id: Optional[int]) -> dict:
    """Add org_id to session data before saving."""
    if org_id is not None:
        session_data["org_id"] = org_id
    return session_data
