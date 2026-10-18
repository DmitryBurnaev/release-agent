from src.db.models import Product


def test_product_has_partial_unique_default_index() -> None:
    index = next(
        index for index in Product.__table__.indexes if index.name == "uq_products_single_default"
    )

    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == "is_default"
    assert str(index.dialect_options["sqlite"]["where"]) == "is_default = 1"
