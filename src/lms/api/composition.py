from sqlalchemy.orm import Session

from lms.catalog.infrastructure.adapters.holding_circulation import HoldingCirculationAdapter
from lms.loan.application.circulation_orchestrator import CirculationOrchestrator
from lms.loan.infrastructure.policy_resolver import PolicyResolver
from lms.reference.infrastructure.adapters.patron_eligibility import PatronEligibilityAdapter
from lms.shared.auth.deps import DbSession


def get_circulation_orchestrator(session: DbSession) -> CirculationOrchestrator:
    return _build_orchestrator(session)


def _build_orchestrator(session: Session) -> CirculationOrchestrator:
    return CirculationOrchestrator(
        session=session,
        patron_eligibility=PatronEligibilityAdapter(session),
        holding_circulation=HoldingCirculationAdapter(session),
        policy_resolver=PolicyResolver(session),
    )
