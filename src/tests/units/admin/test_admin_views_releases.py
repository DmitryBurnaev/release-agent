from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqladmin.filters import ForeignKeyFilter
from sqlalchemy.dialects import postgresql

from src.db.models import Product, Release
from src.modules.admin.views.releases import ReleaseAdminView


class TestReleaseAdminView:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("product_count", "expects_filter"),
        [(0, False), (1, False), (2, True)],
    )
    async def test_get_filters_depends_on_product_count(
        self, product_count: int, expects_filter: bool
    ) -> None:
        session = MagicMock()
        session.scalar = AsyncMock(return_value=product_count)
        uow = MagicMock(session=session)
        uow_context = MagicMock()
        uow_context.__aenter__ = AsyncMock(return_value=uow)
        uow_context.__aexit__ = AsyncMock(return_value=None)
        view = ReleaseAdminView()

        with patch(
            "src.modules.admin.views.releases.SASessionUOW",
            return_value=uow_context,
        ):
            await view.list_context(MagicMock())

        filters = view.get_filters()

        session.scalar.assert_awaited_once()
        query = session.scalar.call_args.args[0]
        compiled = str(
            query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "SELECT count(*)" in compiled
        assert "FROM products" in compiled
        assert "LIMIT 2" in compiled
        assert bool(filters) is expects_filter
        if not expects_filter:
            return

        product_filter = filters[0]

        assert isinstance(product_filter, ForeignKeyFilter)
        assert product_filter.foreign_key is Release.product_id
        assert product_filter.foreign_display_field is Product.name
        assert product_filter.title == "Продукт"
