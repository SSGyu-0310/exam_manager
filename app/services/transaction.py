#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transaction Management Module

Provides utilities for consistent transaction boundaries across services.
Defines the principle: "Where should commit happen?" (service layer).

Usage:
    with transaction():
        object = Model(field=value)
        db.session.add(object)
        # commit happens automatically on success, rollback on error
"""

import logging
from contextlib import contextmanager
from typing import Callable, TypeVar, Optional, Any
from functools import wraps

from flask import current_app
from sqlalchemy import exc as sa_exc

from app import db

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextmanager
def transaction():
    """
    Context manager for database transactions.

    Commits on success, rolls back on exception.
    Provides consistent transaction boundaries across services.

    Usage:
        with transaction():
            object = Model(field=value)
            db.session.add(object)
            # No explicit commit needed - handled by context manager
    """
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Transaction rolled back: %s", str(e))
        raise


def transactional(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for transactional function/method.

    Wraps function execution in a transaction context.
    Commits on success, rolls back on exception.

    Usage:
        @transactional
        def create_lecture(name: str) -> Lecture:
            lecture = Lecture(name=name)
            db.session.add(lecture)
            return lecture
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            logger.error("Transaction rolled back in %s: %s", func.__name__, str(e))
            raise

    return wrapper


def safe_commit() -> bool:
    """
    Execute a single commit with error handling.

    Returns True on success, False on failure.
    Logs errors for debugging.

    Usage:
        if safe_commit():
            # proceed with post-commit logic
            pass
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error("Safe commit failed: %s", str(e))
        return False


class TransactionScope:
    """
    Transaction scope manager with explicit commit control.

    Provides more control over when commits happen.

    Usage:
        scope = TransactionScope()
        object = Model(field=value)
        db.session.add(object)
        scope.commit()
    """

    def __init__(self, auto_commit: bool = False):
        self.auto_commit = auto_commit
        self._committed = False
        self._rolled_back = False

    def __enter__(self):
        self._committed = False
        self._rolled_back = False
        return self

    def commit(self) -> bool:
        if self._committed:
            return True
        try:
            db.session.commit()
            self._committed = True
            return True
        except Exception as e:
            db.session.rollback()
            self._rolled_back = True
            logger.error("TransactionScope commit failed: %s", str(e))
            return False

    def rollback(self) -> None:
        if self._rolled_back:
            return
        db.session.rollback()
        self._rolled_back = True
        self._committed = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if not self._rolled_back:
                db.session.rollback()
                self._rolled_back = True
                logger.error("TransactionScope rolled back on exception")
            return

        if self.auto_commit and not self._committed and not self._rolled_back:
            self.commit()


__all__ = [
    "transaction",
    "transactional",
    "safe_commit",
    "TransactionScope",
]
