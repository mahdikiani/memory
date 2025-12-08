"""Utility functions for the memory service."""


def get_all_subclasses(cls: type) -> list[type]:
    """Get all subclasses of a class."""

    subclasses = cls.__subclasses__()
    return subclasses + [
        sub for subclass in subclasses for sub in get_all_subclasses(subclass)
    ]
