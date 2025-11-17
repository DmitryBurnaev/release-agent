import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import (
    BaseRepository,
    UserRepository,
    TokenRepository,
    FilterT,
)
from src.db.models import User, Token


class TestBaseRepository:
    """Tests for BaseRepository class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock AsyncSession."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        """Create mock User instance."""
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def base_repo(self, mock_session: AsyncMock) -> BaseRepository:
        """Create BaseRepository instance for testing."""

        class TestRepository(BaseRepository):
            model = User

        return TestRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_success(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test successful get operation."""
        base_repo.first = AsyncMock(return_value=mock_user)

        result = await base_repo.get(1)

        assert result == mock_user
        base_repo.first.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_get_not_found(self, base_repo: BaseRepository) -> None:
        """Test get operation when instance not found."""
        base_repo.first = AsyncMock(return_value=None)

        with pytest.raises(NoResultFound):
            await base_repo.get(1)

    @pytest.mark.asyncio
    async def test_first_found(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test first operation when instance found."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (mock_user,)
        base_repo.session.execute = AsyncMock(return_value=mock_result)

        result = await base_repo.first(1)

        assert result == mock_user
        base_repo.session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_first_not_found(self, base_repo: BaseRepository) -> None:
        """Test first operation when instance not found."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        base_repo.session.execute = AsyncMock(return_value=mock_result)

        result = await base_repo.first(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_all_with_filters(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test all operation with filters."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(mock_user,)]
        base_repo.session.execute = AsyncMock(return_value=mock_result)

        # Mock _prepare_statement to avoid complex SQLAlchemy logic
        base_repo._prepare_statement = MagicMock(return_value=MagicMock())

        result = await base_repo.all(username="testuser")

        assert result == [mock_user]
        base_repo.session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create(self, base_repo: BaseRepository) -> None:
        """Test create operation."""
        user_data = {"username": "testuser", "email": "test@example.com"}

        with patch("src.db.repositories.logger") as mock_logger:
            result = await base_repo.create(user_data)

            assert isinstance(result, User)
            base_repo.session.add.assert_called_once_with(result)
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_existing(
        self, base_repo: BaseRepository, mock_user: MagicMock
    ) -> None:
        """Test get_or_create when instance exists."""
        base_repo.first = AsyncMock(return_value=mock_user)

        result = await base_repo.get_or_create(1, {"username": "testuser"})

        assert result == mock_user
        base_repo.first.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test get_or_create when instance doesn't exist."""
        base_repo.first = AsyncMock(return_value=None)
        base_repo.create = AsyncMock(return_value=mock_user)
        base_repo.get = AsyncMock(return_value=mock_user)

        result = await base_repo.get_or_create(1, {"username": "testuser"})

        assert result == mock_user
        base_repo.create.assert_awaited_once_with({"username": "testuser", "id": 1})
        base_repo.get.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_update(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test update operation."""
        update_data = {"username": "newuser", "email": "new@example.com"}

        await base_repo.update(mock_user, **update_data)

        assert mock_user.username == "newuser"
        assert mock_user.email == "new@example.com"
        base_repo.session.add.assert_called_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_delete(self, base_repo: BaseRepository, mock_user: MagicMock) -> None:
        """Test delete operation."""
        await base_repo.delete(mock_user)

        base_repo.session.delete.assert_awaited_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_delete_by_ids(self, base_repo: BaseRepository) -> None:
        """Test delete_by_ids operation."""
        ids = [1, 2, 3]

        await base_repo.delete_by_ids(ids)

        base_repo.session.execute.assert_awaited_once()

    def test_prepare_statement_with_ids_filter(self, base_repo: BaseRepository) -> None:
        """Test _prepare_statement with ids filter."""
        filters: dict[str, FilterT] = {"ids": [1, 2, 3], "username": "testuser"}

        base_repo._prepare_statement(filters)

        assert "ids" not in filters  # Should be popped from filters

    def test_prepare_statement_without_ids_filter(self, base_repo: BaseRepository) -> None:
        """Test _prepare_statement without ids filter."""
        filters: dict[str, FilterT] = {"username": "testuser"}

        base_repo._prepare_statement(filters)

        assert "username" in filters

    def test_prepare_statement_with_entities(self, base_repo: BaseRepository) -> None:
        """Test _prepare_statement with custom entities."""
        filters: dict[str, FilterT] = {"username": "testuser"}
        entities = [User.id, User.username]

        statement = base_repo._prepare_statement(filters, entities)

        # Should not raise any exceptions
        assert statement is not None


class TestUserRepository:
    """Tests for UserRepository class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock AsyncSession."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def user_repo(self, mock_session: AsyncMock) -> UserRepository:
        """Create UserRepository instance."""
        return UserRepository(mock_session)

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        """Create mock User instance."""
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        return user

    @pytest.mark.asyncio
    async def test_get_by_username_found(
        self, user_repo: UserRepository, mock_user: MagicMock
    ) -> None:
        """Test get_by_username when user found."""
        user_repo.all = AsyncMock(return_value=[mock_user])

        with patch("src.db.repositories.logger") as mock_logger:
            result = await user_repo.get_by_username("testuser")

            assert result == mock_user
            user_repo.all.assert_awaited_once_with(username="testuser")
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, user_repo: UserRepository) -> None:
        """Test get_by_username when user not found."""
        user_repo.all = AsyncMock(return_value=[])

        with patch("src.db.repositories.logger") as mock_logger:
            result = await user_repo.get_by_username("nonexistent")

            assert result is None
            user_repo.all.assert_awaited_once_with(username="nonexistent")
            mock_logger.debug.assert_called_once()


class TestTokenRepository:
    """Tests for TokenRepository class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock AsyncSession."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def token_repo(self, mock_session: AsyncMock) -> TokenRepository:
        """Create TokenRepository instance."""
        return TokenRepository(mock_session)

    @pytest.fixture
    def mock_token(self) -> MagicMock:
        """Create mock Token instance."""
        token = MagicMock(spec=Token)
        token.id = 1
        token.token = "hashed_token_value"
        token.is_active = True
        return token

    @pytest.mark.asyncio
    async def test_get_by_token_found(
        self, token_repo: TokenRepository, mock_token: MagicMock
    ) -> None:
        """Test get_by_token when token found."""
        token_repo.all = AsyncMock(return_value=[mock_token])

        with patch("src.db.repositories.logger") as mock_logger:
            result = await token_repo.get_by_token("hashed_token_value")

            assert result == mock_token
            token_repo.all.assert_awaited_once_with(token="hashed_token_value")
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_token_not_found(self, token_repo: TokenRepository) -> None:
        """Test get_by_token when token not found."""
        token_repo.all = AsyncMock(return_value=[])

        with patch("src.db.repositories.logger") as mock_logger:
            result = await token_repo.get_by_token("nonexistent")

            assert result is None
            token_repo.all.assert_awaited_once_with(token="nonexistent")
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_active_true(self, token_repo: TokenRepository) -> None:
        """Test set_active with is_active=True."""
        token_ids = [1, 2, 3]
        mock_result = MagicMock()
        mock_result.rowcount = 3
        token_repo.session.execute = AsyncMock(return_value=mock_result)
        token_repo.session.flush = AsyncMock()

        with patch("src.db.repositories.logger") as mock_logger:
            await token_repo.set_active(token_ids, True)

            token_repo.session.execute.assert_awaited_once()
            token_repo.session.flush.assert_awaited_once()

            # Check log calls
            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call("[DB] %s tokens: %r", "Activating", [1, 2, 3])
            mock_logger.info.assert_any_call("[DB] %s %d tokens", "Activated", 3)

    @pytest.mark.asyncio
    async def test_set_active_false(self, token_repo: TokenRepository) -> None:
        """Test set_active with is_active=False."""
        token_ids = [1, 2, 3]
        mock_result = MagicMock()
        mock_result.rowcount = 2
        token_repo.session.execute = AsyncMock(return_value=mock_result)
        token_repo.session.flush = AsyncMock()

        with patch("src.db.repositories.logger") as mock_logger:
            await token_repo.set_active(token_ids, False)

            token_repo.session.execute.assert_awaited_once()
            token_repo.session.flush.assert_awaited_once()

            # Check log calls
            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call("[DB] %s tokens: %r", "Deactivating", [1, 2, 3])
            mock_logger.info.assert_any_call("[DB] %s %d tokens", "Deactivated", 2)

    @pytest.mark.asyncio
    async def test_set_active_with_string_ids(self, token_repo: TokenRepository) -> None:
        """Test set_active with string IDs."""
        token_ids = ["1", "2", "3"]
        mock_result = MagicMock()
        mock_result.rowcount = 3
        token_repo.session.execute = AsyncMock(return_value=mock_result)
        token_repo.session.flush = AsyncMock()

        with patch("src.db.repositories.logger"):
            await token_repo.set_active(token_ids, True)

            token_repo.session.execute.assert_awaited_once()
            token_repo.session.flush.assert_awaited_once()
