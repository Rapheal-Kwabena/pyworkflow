"""Plugin architecture: a plugin packages up one or more reusable Task
factories (e.g. "send an email", "run a SQL query") that can be registered
once and reused across workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """Base class for a PyWorkflow plugin.

    Subclasses should implement `name` and provide one or more methods that
    return :class:`~pyworkflow.core.task.Task` instances ready to add to a
    workflow.
    """

    name: str = "unnamed_plugin"

    @abstractmethod
    def setup(self, **config: Any) -> None:
        """Configure the plugin (e.g. store API credentials)."""


class PluginRegistry:
    """A simple in-memory registry mapping plugin name -> instance."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin:
        if name not in self._plugins:
            raise KeyError(f"No plugin registered under name '{name}'")
        return self._plugins[name]

    def list(self) -> list[str]:
        return sorted(self._plugins.keys())


registry = PluginRegistry()


class PluginManager:
    """Compatibility manager to register and store plugin references."""

    def __init__(self) -> None:
        self.plugins: dict[str, Any] = {}

    def register(self, plugin_name: str) -> None:
        from pyworkflow.plugins.email import EmailPlugin
        from pyworkflow.plugins.database import DatabasePlugin
        from pyworkflow.plugins.api import APIPlugin
        from pyworkflow.plugins.ai import AIPlugin

        mapping = {
            "email": EmailPlugin,
            "database": DatabasePlugin,
            "api": APIPlugin,
            "ai": AIPlugin,
        }

        if plugin_name in mapping:
            plugin_inst = mapping[plugin_name]()  # type: ignore[abstract]
            self.plugins[plugin_name] = plugin_inst
            registry.register(plugin_inst)
        else:
            self.plugins[plugin_name] = plugin_name
