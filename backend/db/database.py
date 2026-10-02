"""Neon Postgres access. Use the *pooled* Neon connection string (host has '-pooler')."""
import os, json, datetime, decimal
from contextlib import contextmanager
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg.types.numeric import FloatLoader

load_dotenv()
_pool = None


def _configure(conn):
    conn.adapters.register_loader("numeric", FloatLoader)  # NUMERIC -> float (JSON friendly)


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1, max_size=5, max_idle=60,
            kwargs={"row_factory": dict_row},
            configure=_configure,
            check=ConnectionPool.check_connection,  # Neon scales to zero; drop dead connections
            open=True,
        )
    return _pool


def _default(o):
    if isinstance(o, (datetime.date, datetime.datetime, datetime.time)):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def J(obj):
    """Wrap a python object for a JSONB column."""
    return Jsonb(obj, dumps=lambda o: json.dumps(o, default=_default))


def jsonable(obj):
    return json.loads(json.dumps(obj, default=_default))


@contextmanager
def transaction():
    """One transaction: commits on success, rolls back on exception."""
    with pool().connection() as conn:
        yield conn


def q(sql, params=None, conn=None):
    if conn is not None:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []
    with pool().connection() as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else []


def one(sql, params=None, conn=None):
    rows = q(sql, params, conn)
    return rows[0] if rows else None
