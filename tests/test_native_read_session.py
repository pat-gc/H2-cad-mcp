from types import SimpleNamespace

import pytest

from h2cad.backend import Unsupported
from h2cad.model import Target
from h2cad.native_read_session import NativeReadSession


@pytest.mark.asyncio
async def test_read_session_rejects_mutation_before_transport():
    class Bridge:
        async def command(self, job):
            pytest.fail("Read-only transport dispatched an editor operation")
    session = NativeReadSession(SimpleNamespace(bridge=Bridge(), tab_id=1),
        Target("a"*24,"b"*24,"c"*24), "d"*24, lambda state: None)
    with pytest.raises(Unsupported, match="read command"):
        await session.native("ui.GBTUiCommitFeature", {})
    with pytest.raises(Unsupported, match="read schema"):
        await session.schema("ui.GBTUiCommitFeature", set())
    assert session.reads == session.schemas == []
