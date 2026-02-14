from __future__ import annotations

from app.models import Block, Lecture


def block_ordering():
    return (Block.subject.is_(None), Block.subject, Block.order, Block.name)


def block_lecture_ordering():
    return (Block.subject.is_(None), Block.subject, Block.order, Lecture.order)
