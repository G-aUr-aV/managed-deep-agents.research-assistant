"""Durable memory shared by every caller and preserved across redeployments."""

from managed_deepagents import define_memory

memory = define_memory(scope="agent")
