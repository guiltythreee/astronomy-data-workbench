"""Exceptions raised for problems that stop a run (as opposed to row-level issues)."""


class SourceError(Exception):
    """The input file cannot be read or decoded."""


class SchemaError(Exception):
    """The input file does not have the structure the parser requires."""
