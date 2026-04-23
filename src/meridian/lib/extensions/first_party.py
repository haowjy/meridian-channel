"""First-party extension command registrations."""

from meridian.lib.extensions.registry import ExtensionCommandRegistry


def register_first_party_commands(registry: ExtensionCommandRegistry) -> None:
    """Register all v1 first-party commands."""

    from meridian.lib.extensions.commands.sessions import (
        ARCHIVE_SPAWN_SPEC,
        GET_SPAWN_STATS_SPEC,
    )
    from meridian.lib.extensions.commands.workbench import PING_SPEC
    from meridian.lib.extensions.ops_bridge import register_operations

    registry.register(ARCHIVE_SPAWN_SPEC)
    registry.register(GET_SPAWN_STATS_SPEC)
    registry.register(PING_SPEC)
    register_operations(registry)
