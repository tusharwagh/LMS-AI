from fastapi import APIRouter, Depends

from lms.api.deps import require_auth
from lms.api.llm_spend.router import router as llm_spend_router
from lms.api.workflows.router import router as workflows_router
from lms.catalog.api.router import router as catalog_router
from lms.loan.api.router import router as loan_router
from lms.reference.api.router import router as reference_router
from lms.reporting.api.router import router as reporting_router

# Every domain route requires a valid Bearer JWT (Reference, Catalog, Loan).
domain_api_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_auth)],
)

domain_api_router.include_router(reference_router, prefix="/reference", tags=["reference"])
domain_api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
domain_api_router.include_router(loan_router, prefix="/loan", tags=["loan"])
domain_api_router.include_router(workflows_router, tags=["workflows"])
domain_api_router.include_router(llm_spend_router, tags=["llm-spend"])
domain_api_router.include_router(reporting_router, tags=["reporting"])
