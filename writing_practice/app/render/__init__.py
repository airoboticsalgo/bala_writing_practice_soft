"""Worksheet rendering: shape -> outline -> paint, straight to vector PDF."""

from .page import render_worksheet
from .spec import SpecError, WorksheetSpec, from_form

__all__ = ["render_worksheet", "WorksheetSpec", "SpecError", "from_form"]
