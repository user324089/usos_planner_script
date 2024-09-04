"""
Module containing the PlannerUnit class and functions related to it.
"""
import pathlib
from dataclasses import dataclass, field
import usos_tools.timetables as tt


@dataclass
class PlannerUnit:
    """
    Class representing a timetable planner unit.
    Contains all necessary data to create and optimize timetables.
    """
    name: str = 'unnamed'
    evaluator: str = 'time'
    # all attended courses
    courses: set[str] = field(default_factory=set)
    # map from course code and type to groups
    groups: dict[str, dict[str, list[tt.GroupEntry]]] = field(default_factory=dict)
    config_path: pathlib.Path = field(default_factory=pathlib.Path)

    ranked_timetables: list[tuple[list[tt.GroupEntry], float]] = field(default_factory=list)

    template_timetable_id: int = -1

    def __str__(self):
        return 'name: ' + self.name + ' evaluator: ' + self.evaluator


