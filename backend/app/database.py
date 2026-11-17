import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tracefront:tracefront@localhost:5432/tracefront")

engine = create_engine(DATABASE_URL, **({"connect_args": {"check_same_thread": False}}
                                      if DATABASE_URL.startswith("sqlite") else {}))

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def add_missing_columns(bind=engine) -> None:
    """`create_all` creates new tables but never adds a column to a table that already exists. Add those here, so a
    model can gain an optional column without a side table.

    ponytail: additive only, and safe to run on every start. Renaming or retyping a column, dropping a constraint or
    rewriting data needs a real migration tool (Alembic) and a rehearsal on a copy of the database.
    """
    inspector = inspect(bind)
    quote = bind.dialect.identifier_preparer.quote
    with bind.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            stored = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in stored:
                    continue
                if not column.nullable:
                    raise RuntimeError(f"{table.name}.{column.name} is required, so existing rows cannot receive it "
                                       "automatically; write a migration")
                connection.execute(text(f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} "
                                        f"{column.type.compile(bind.dialect)}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
