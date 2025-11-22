import dataclasses

from sqlalchemy.ext.asyncio import AsyncSession

from src.db import ReleaseRepository


@dataclasses.dataclass(frozen=True)
class DashboardCounts:
    total_releases: int
    active_releases: int
    inactive_releases: int


class AdminCounter:
    """Admin's dashboard aggregations"""

    @classmethod
    async def get_stat(cls, session: AsyncSession) -> DashboardCounts:
        """Get releases counts"""
        release_repository = ReleaseRepository(session)
        releases = await release_repository.group_by_active()

        return DashboardCounts(
            total_releases=releases.active + releases.inactive,
            active_releases=releases.active,
            inactive_releases=releases.inactive,
        )
