from sqladmin.filters import ForeignKeyFilter

from src.db.models import Product, Release
from src.modules.admin.views.releases import ReleaseAdminView


class TestReleaseAdminView:
    def test_product_filter_uses_product_name_for_labels(self) -> None:
        product_filter = ReleaseAdminView.column_filters[0]

        assert isinstance(product_filter, ForeignKeyFilter)
        assert product_filter.foreign_key is Release.product_id
        assert product_filter.foreign_display_field is Product.name
        assert product_filter.title == "Продукт"
