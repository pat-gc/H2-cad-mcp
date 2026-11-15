"""Shared revision-pinned transport for native geometry and scope inspection."""
from __future__ import annotations

import copy

from .backend import Unsupported


class NativeReadSession:
    """Record read provenance and recheck caller-specific saved/draft state."""

    COMMANDS = frozenset({"ui.document.GBTUiQueryInsertables", "ui.GBTUiGetQueryDataCall", "ui.GBTUiMassPropCall"})

    def __init__(self, backend, target, document_revision, check_state):
        self.backend = backend
        self.target = target
        self.document_revision = document_revision
        self.check_state = check_state
        self.schemas = []
        self.reads = []

    async def schema(self, name, required):
        if name not in self.COMMANDS | {"bsedit.GBTMIndividualQuery"}:
            raise Unsupported("Unsupported native read schema")
        response = await self.backend.bridge.command({"kind": "schema", "target": self.target.to_dict(),
            "tab_id": self.backend.tab_id, "name": name})
        defaults = response.get("defaults")
        if (response.get("name") != name or not isinstance(defaults, dict)
                or defaults.get("$type") != name or set(defaults) != {"$type"} | set(required)):
            raise Unsupported("Native measurement schema differs from observed fields: " + name)
        self.schemas.append(copy.deepcopy(response))
        return {key: copy.deepcopy(value) for key, value in defaults.items() if key != "$type"}

    async def native(self, name, body):
        if name not in self.COMMANDS:
            raise Unsupported("Unsupported native read command")
        response = await self.backend.bridge.command({"kind": "native", "target": self.target.to_dict(),
            "tab_id": self.backend.tab_id, "command": name, "body": body})
        result = response.get("result")
        if (not isinstance(result, dict) or any(response.get(key) for key in ("error", "errorCode", "errorEnum"))
                or any(result.get(key) for key in ("error", "errorCode", "errorEnum"))
                or response.get("microversion_before") != self.document_revision
                or response.get("microversion_after") != self.document_revision):
            raise Unsupported("Native read failed or document revision changed")
        self.check_state(await self.backend.raw_state(self.target))
        self.reads.append({"command": name, "body": copy.deepcopy(body), "response": copy.deepcopy(response)})
        return response
