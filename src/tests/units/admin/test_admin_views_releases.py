from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqladmin.filters import ForeignKeyFilter

from src.db.models import Product, Release
from src.modules.admin.views.releases import ReleaseAdminView


class TestReleaseAdminView:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("product_ids", "expects_filter"),
        [([1], False), ([1, 2], True)],
    )
    async def test_get_filters_depends_on_product_count(
        self, product_ids: list[int], expects_filter: bool
    ) -> None:
        session = MagicMock()
        product_id_result = MagicMock()
        product_id_result.all.return_value = product_ids
        session.scalars = AsyncMock(return_value=product_id_result)
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

        assert bool(filters) is expects_filter
        if not expects_filter:
            return

        product_filter = filters[0]

        assert isinstance(product_filter, ForeignKeyFilter)
        assert product_filter.foreign_key is Release.product_id
        assert product_filter.foreign_display_field is Product.name
        assert product_filter.title == "Продукт"
