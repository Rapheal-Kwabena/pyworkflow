"""Built-in plugins that turn common integrations (email, DB, HTTP, AI) into
reusable Task factories, plus the base Plugin/PluginRegistry classes for
writing your own."""

from pyworkflow.plugins.ai import AIPlugin
from pyworkflow.plugins.api import APIPlugin
from pyworkflow.plugins.base import Plugin, PluginRegistry, registry, PluginManager
from pyworkflow.plugins.database import DatabasePlugin
from pyworkflow.plugins.email import EmailPlugin

__all__ = [
    "Plugin",
    "PluginRegistry",
    "registry",
    "PluginManager",
    "EmailPlugin",
    "DatabasePlugin",
    "APIPlugin",
    "AIPlugin",
]
