"""PostgreSQL database client for local development.

This module provides a connection pool and helper functions for interacting with
a local PostgreSQL database as an alternative to Supabase for development/demo purposes.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore
    pool = None  # type: ignore
    RealDictCursor = None  # type: ignore


class PostgresClient:
    """PostgreSQL database client with connection pooling."""

    def __init__(self) -> None:
        """Initialize PostgreSQL connection pool."""
        self.enabled = os.getenv("USE_LOCAL_DB", "0") == "1"
        self._pool: Any = None

        if self.enabled and psycopg2 is not None:
            try:
                self._pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=os.getenv("POSTGRES_HOST", "localhost"),
                    port=int(os.getenv("POSTGRES_PORT", "5432")),
                    database=os.getenv("POSTGRES_DB", "chromakit"),
                    user=os.getenv("POSTGRES_USER", "chromakit"),
                    password=os.getenv("POSTGRES_PASSWORD", "chromakit_dev_password"),
                )
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(f"Failed to initialize PostgreSQL connection pool: {exc}") from exc

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a database connection from the pool.

        Yields:
            Database connection with automatic return to pool on exit.

        Raises:
            RuntimeError: If local database is not enabled or connection fails.
        """
        if not self.enabled or self._pool is None:
            raise RuntimeError("Local PostgreSQL database is not enabled")

        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True) -> Generator[Any, None, None]:
        """Get a database cursor.

        Args:
            dict_cursor: If True, returns results as dictionaries (default: True).

        Yields:
            Database cursor.
        """
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def execute_one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        """Execute a query and return a single result.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Single row as dictionary or None if no results.
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None

    def execute_many(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a query and return all results.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            List of rows as dictionaries.
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def execute_insert(self, query: str, params: tuple = ()) -> dict[str, Any]:
        """Execute an INSERT query and return the inserted row.

        Args:
            query: SQL INSERT query with RETURNING clause.
            params: Query parameters.

        Returns:
            Inserted row as dictionary.
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            if not result:
                raise RuntimeError("Insert query did not return a row")
            return dict(result)

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an UPDATE or DELETE query.

        Args:
            query: SQL UPDATE or DELETE query.
            params: Query parameters.

        Returns:
            Number of rows affected.
        """
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()


# Singleton instance
_POSTGRES_CLIENT: PostgresClient | None = None


def get_postgres_client() -> PostgresClient | None:
    """Get PostgreSQL client singleton.

    Returns:
        PostgresClient instance if enabled, None otherwise.
    """
    global _POSTGRES_CLIENT
    if os.getenv("USE_LOCAL_DB", "0") != "1":
        return None
    if _POSTGRES_CLIENT is None:
        _POSTGRES_CLIENT = PostgresClient()
    return _POSTGRES_CLIENT
