from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.database import Base
from config.lifecycle import init_create_table


@pytest.mark.asyncio
async def test_init_create_table_uses_registry_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = SimpleNamespace(run_sync=AsyncMock())

    @asynccontextmanager
    async def connection_context() -> AsyncGenerator[object, None]:
        yield connection

    registry = SimpleNamespace(connection=connection_context)
    monkeypatch.setattr('config.lifecycle.DataSourceRegistry', registry)

    await init_create_table(log_success_enabled=False)

    call = connection.run_sync.await_args
    assert call.args == (Base.metadata.create_all,)
    assert all(not table.name.startswith('fb_') for table in call.kwargs['tables'])
    assert set(call.kwargs['tables']) == {
        table for table in Base.metadata.tables.values() if not table.name.startswith('fb_')
    }
