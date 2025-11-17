import dataclasses

from sqlalchemy.ext.asyncio import AsyncSession


@dataclasses.dataclass(frozen=True)
class DashboardCounts:
    total_releases: int
    active_releases: int


class AdminCounter:
    """Admin's dashboard aggregations"""

    @classmethod
    async def get_stat(cls, session: AsyncSession) -> DashboardCounts:
        """Get releases counts"""
        return DashboardCounts(
            total_releases=10,
            active_releases=5,
        )
