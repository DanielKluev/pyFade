"""Shared declarative base for all dataset ORM models."""

from __future__ import annotations

from sqlalchemy.orm import declarative_base

dataset_base = declarative_base()
