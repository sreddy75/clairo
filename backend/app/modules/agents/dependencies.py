"""FastAPI dependencies for the agents module."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.agents.orchestrator import MultiPerspectiveOrchestrator
from app.modules.agents.settings import AgentSettings, agent_settings


def get_agent_settings() -> AgentSettings:
    """Get agent settings singleton.

    Returns:
        AgentSettings instance.
    """
    return agent_settings


def get_orchestrator(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MultiPerspectiveOrchestrator:
    """Get orchestrator instance with database session.

    Args:
        db: Injected database session.

    Returns:
        MultiPerspectiveOrchestrator instance.
    """
    return MultiPerspectiveOrchestrator(db)


# Type aliases for dependency injection
OrchestratorDep = Annotated[MultiPerspectiveOrchestrator, Depends(get_orchestrator)]
AgentSettingsDep = Annotated[AgentSettings, Depends(get_agent_settings)]
