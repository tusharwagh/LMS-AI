from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from lms.config import get_settings
from lms.shared.db.base import Base

# Import models so Alembic autogenerate sees metadata (expand per phase).
from lms.shared.idempotency.store import IdempotencyRecord  # noqa: F401
from lms.reference.infrastructure.models.models import (  # noqa: F401
    ClassSectionModel,
    PatronBlockModel,
    PatronModel,
    PatronTypeModel,
)
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel  # noqa: F401
from lms.loan.infrastructure.models.models import (  # noqa: F401
    CirculationFulfillmentModel,
    LoanModel,
    LoanRuleSetModel,
)
from lms.platform.infrastructure.models.api_user import ApiUserModel  # noqa: F401
from lms.shared.llm.spend import LlmSpendLog  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
