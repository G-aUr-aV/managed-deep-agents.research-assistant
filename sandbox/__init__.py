"""Managed LangSmith sandbox declaration.

MDA owns the run-scoped name, reuse across turns, and lifecycle. Delete this
directory to run without a sandbox.
"""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(
    # One sandbox per conversation thread, reused across turns.
    scope="thread",
    # Reclaim idle sandboxes after 10 minutes.
    idle_ttl_seconds=600,
    # Default per-command timeout, in seconds.
    default_timeout=600,
)
