"""Pytest configuration and fixtures for db tests."""

import pytest


@pytest.fixture
def sample_embedding() -> list[float]:
    """Sample embedding vector for testing."""
    return [0.1, 0.2, 0.3, 0.4, 0.5]


@pytest.fixture
def sample_entity_ids() -> list[str]:
    """Sample entity IDs for testing."""
    return ["entity:1", "entity:2", "entity:3"]


@pytest.fixture
def sample_table() -> str:
    """Sample table name for testing."""
    return "test_table"
