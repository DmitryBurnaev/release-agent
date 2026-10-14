from importlib import import_module
from unittest.mock import MagicMock, patch


def test_products_migration_creates_default_flag_and_partial_unique_index() -> None:
    migration = import_module("src.migrations.versions.0004_products")
    operations = MagicMock()

    with patch.object(migration, "op", operations):
        migration.upgrade()

    product_columns = operations.create_table.call_args.args[1:]
    default_column = next(column for column in product_columns if column.name == "is_default")
    assert default_column.nullable is False
    assert str(default_column.server_default.arg) == "false"

    index_call = next(
        call
        for call in operations.create_index.call_args_list
        if call.args[0] == "uq_products_single_default"
    )
    assert index_call.args[1:3] == ("products", ["is_default"])
    assert index_call.kwargs["unique"] is True
    assert str(index_call.kwargs["postgresql_where"]) == "is_default"

    executed_sql = [str(call.args[0]) for call in operations.execute.call_args_list]
    assert "INSERT INTO products (name, is_default) VALUES ('default', true)" in executed_sql
    assert any("products.is_default IS TRUE" in statement for statement in executed_sql)
