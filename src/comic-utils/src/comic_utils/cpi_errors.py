# ruff: noqa: ANN204, E501, EXE001, EXE005, D105, D200, D212, N818, PIE790

#! /usr/bin/env python
"""
Custom errors.
"""


class CPIObjectDoesNotExist(Exception):
    """
    Error raised when a CPI object is requested that doesn't exist.
    """

    pass


class StaleDataWarning(Warning):
    """
    The warning to raise when the local data are out of date.
    """

    def __str__(self):
        # noinspection LongLine
        return "CPI data is out of date. To accurately inflate to today's dollars, you must run `cpi.update()`."
