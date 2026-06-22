"""Shared JWT + RBAC dependencies for domain API routers."""

from typing import Annotated

from fastapi import Depends

from lms.api.deps import require_auth, require_roles
from lms.platform.auth.roles import Role
from lms.shared.auth.jwt import AuthContext

# JWT required — any authenticated API user.
AuthenticatedAuth = Annotated[AuthContext, Depends(require_auth)]

# Staff desk operations (MVP §13.4).
StaffAuth = Annotated[AuthContext, Depends(require_roles(Role.ADMIN, Role.LIBRARIAN))]

# Admin configuration (loan rules, patron types, class setup).
AdminAuth = Annotated[AuthContext, Depends(require_roles(Role.ADMIN))]

# Reusable Depends() for router-level declarations.
require_staff = Depends(require_roles(Role.ADMIN, Role.LIBRARIAN))
require_admin = Depends(require_roles(Role.ADMIN))
require_authenticated = Depends(require_auth)
