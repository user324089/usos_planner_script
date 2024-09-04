"""
This module contains utility functions for the planner.
"""
import pathlib
from scripts.utils import read_words_from_file

from .evaluators import EVALUATORS


COURSE_TERMS: dict[str, str] = {}

def read_dydactic_cycle() -> str:
    """Returns the dydactic cycle."""
    if words := read_words_from_file('./config/cycle'):
        return words[0]
    raise RuntimeError('Failed to read dydactic cycle')


def read_personal_config(path: pathlib.Path) -> tuple[set[str], str]:
    """Returns courses and evaluator specified in personal config directory."""
    courses = set(read_words_from_file(str((path / 'codes').resolve())))

    words = read_words_from_file(str((path / 'eval').resolve()))
    if len(words) == 1 and ((evaluator := words[0]) in EVALUATORS):
        return courses, evaluator
    raise RuntimeError('Failed to read evaluator function')
