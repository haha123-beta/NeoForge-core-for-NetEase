# -*- coding: utf-8 -*-
"""Conservative numeric Maven-range subset; unsupported syntax is an error."""
from __future__ import absolute_import
import re


def numeric_version(value):
    if not re.match(r"^[0-9]+(\.[0-9]+)*$", value):
        raise ValueError("Unsupported non-numeric version: " + str(value))
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def compare(left, right):
    length = max(len(left), len(right))
    left = left + (0,) * (length - len(left))
    right = right + (0,) * (length - len(right))
    return (left > right) - (left < right)


def matches(version, requirement):
    if not requirement:
        return True
    requirement = requirement.strip()
    if requirement.startswith("[") and requirement.endswith("]") and "," not in requirement:
        return compare(numeric_version(version), numeric_version(requirement[1:-1])) == 0
    if (len(requirement) < 3 or requirement[0] not in "[(" or
            requirement[-1] not in "])" or requirement.count(",") != 1):
        raise ValueError("Unsupported version range: " + requirement)
    low, high = [part.strip() for part in requirement[1:-1].split(",")]
    lower = numeric_version(low) if low else None
    upper = numeric_version(high) if high else None
    if not low and requirement[0] != "(" or not high and requirement[-1] != ")":
        raise ValueError("Unbounded endpoints must be open")
    if lower is not None and upper is not None and compare(lower, upper) > 0:
        raise ValueError("Reversed version range")
    value = numeric_version(version)
    if lower is not None:
        cmp = compare(value, lower)
        if cmp < 0 or (cmp == 0 and requirement[0] == "("):
            return False
    if upper is not None:
        cmp = compare(value, upper)
        if cmp > 0 or (cmp == 0 and requirement[-1] == ")"):
            return False
    return True
