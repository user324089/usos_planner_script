import math
import usos_tools.timetables as tt

from .plannerunit import PlannerUnit
from .evaluators import EVALUATORS


def list_possible_timetables(all_course_units: dict[str, dict[str, list[tt.GroupEntry]]]):
    """
    Returns a list of all timeables with no colliding groups that contain every course.
    :param all_course_units: [course][classtype] -> list of groups
    :return: list of timetables
    """
    current_timetables: list[list[tt.GroupEntry]] = [[]]
    for groups_with_same_name in all_course_units.values():
        # course unit is a class type (like WYK/CW) associated with a course,
        # that consists of groups
        for groups in groups_with_same_name.values():
            new_timetables: list[list[tt.GroupEntry]] = []
            for curr_timetable in current_timetables:
                for new_group in groups:
                    if not any(tt.do_groups_collide(new_group, curr_group)
                               for curr_group in curr_timetable):
                        new_timetables.append(curr_timetable.copy() + [new_group])
            current_timetables = new_timetables

    print(str(len(current_timetables)) + " possible timetables found")
    return current_timetables


def _min_normalize(values: list[int]) -> list[float]:
    """Returns a list of values divided by the minimum value."""
    if not values:
        return []
    min_value = min(values)
    return [value / min_value for value in values]


def get_top_timetables(planner_unit: PlannerUnit, n: int | None = None
                       ) -> list[tuple[list[tt.GroupEntry], float]]:
    """Returns top n timetables with scores for a given planner unit."""
    possible_timetables = list_possible_timetables(planner_unit.groups)

    timetable_scores = [
        EVALUATORS[planner_unit.evaluator](timetable, planner_unit.config_path)
        for timetable in possible_timetables
    ]
    timetable_scores = _min_normalize(timetable_scores)
    timetables_with_scores = list(zip(possible_timetables, timetable_scores))

    # sort timetables by badness
    timetables_with_scores.sort(key=lambda x: x[1])

    # return top n
    if n is None:
        return timetables_with_scores
    return timetables_with_scores[:n]


def groups_fit(subset: list[tt.GroupEntry], superset: list[tt.GroupEntry]) -> bool:
    """Returns True if common courses in subset and superset have the same groups."""
    superset_map: dict[tuple[str, str], tt.GroupEntry]
    superset_map = {(group.course, group.classtype): group for group in superset}

    for subset_entry in subset:
        subset_key = (subset_entry.course, subset_entry.classtype)
        if subset_key in superset_map and superset_map[subset_key] != subset_entry:
            return False
    return True


def get_best_fitting_timetables_individual(
        timetables: list[tuple[list[tt.GroupEntry], float]],
        timetable_to_fit: list[tt.GroupEntry],
        n: int | None = None
) -> tuple[list[int], float]:
    """Returns indices of the best n timetables that fit the timetable_to_fit
    and the total score. Timetables MUST BE SORTED by score."""
    if n is None:
        n = len(timetables)

    fitting_timetables: list[int] = []
    total_score: float = 0

    for index, (timetable, score) in enumerate(timetables):
        if groups_fit(timetable_to_fit, timetable):
            fitting_timetables.append(index)
            total_score += score
            if len(fitting_timetables) == n:
                break
    return fitting_timetables, total_score


def get_best_fitting_timetables_group(
        planner_units: list[PlannerUnit],
        timetable_to_fit: list[tt.GroupEntry],
        n: int
) -> tuple[list[list[int]], float]:
    """Returns a list of the indices of n best fitting timetables
    for each person and the total score."""
    best_timetables_per_person: list[list[int]] = []
    group_score: float = 0

    for planner_unit in planner_units:
        individual_timetables, individual_score = get_best_fitting_timetables_individual(
            planner_unit.ranked_timetables,
            timetable_to_fit,
            n
        )
        # list of timetables for any person should have at least n entries
        if len(individual_timetables) < n:
            return [], math.inf
        # update the group timetables/score
        best_timetables_per_person.append(individual_timetables)
        group_score += individual_score ** 3

    return best_timetables_per_person, group_score
