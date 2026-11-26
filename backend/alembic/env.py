from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, inspect, pool, text

from app.config import settings
from app.db import Base
import app.models  # noqa: F401  注册所有模型

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _reset_stale_version(connectable) -> None:
    """迁移脚本只保留建表脚本；旧库残留的历史版本号需要清空后重新建表。"""
    if not inspect(connectable).has_table("alembic_version"):
        return
    known = {item.revision for item in ScriptDirectory.from_config(config).walk_revisions()}
    with connectable.begin() as connection:
        versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if any(version not in known for version in versions):
            connection.execute(text("DELETE FROM alembic_version"))


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
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
    _reset_stale_version(connectable)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
