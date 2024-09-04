"""
This module contains all function related to finding and evaluating tiemtable strategies.
"""
from collections import defaultdict
import jsonpickle
import usos_tools.timetables as tt

from .plannerunit import PlannerUnit


def _timetable_has_group(timetable: list[tt.GroupEntry], group: tt.GroupEntry) -> bool:
    """Returns True if the timetable contains the group."""
    return any(entry == group for entry in timetable)


def _find_group_in_timetable(timetable: list[tt.GroupEntry], course: str, course_unit: str) \
                                                                            -> tt.GroupEntry:
    """
    Returns the group with the given course and course unit from the timetable.
    :param timetable: list of groups in the timetable
    :param course: course code
    :param course_unit: course unit id
    :return: group with the given course and course unit
    """
    for group in timetable:
        if group.course == course and group.classtype == course_unit:
            return group
    raise RuntimeError('Group not found in the timetable')


def _add_group_constraint(
        timetable_ids: list[int],
        planner_unit: PlannerUnit,
        group: tt.GroupEntry
) -> list[int]:
    """
    Returns a list of timetable ids that contain the group.
    :param timetable_ids: list of timetable ids in planner_unit.ranked_timetables
    :param planner_unit: planner unit that contains the timetables
    :param group: group that has to be in the timetable
    :return: list of timetable ids that contain the group
    """
    return [
        timetable_id for timetable_id in timetable_ids
        if _timetable_has_group(planner_unit.ranked_timetables[timetable_id][0], group)
    ]


def _strategy_dfs(
        n: int | None,
        edges: list[tuple[int, int, str, str]],
        timetables: dict[int, list[int]],
        planner_units: list[PlannerUnit]
):
    """
    Returns a strategy tree for the given group graph.
    :param n: number of the best timetables to keep for each planner unit (None keeps all)
    :param edges: list of edges that represent shared groups between people
    :param timetables: dictionary of planner unit id -> list of timetable ids
    (from planner_unit.ranked_timetables)
    :param planner_units: list of planner units
    :return: Strategy DFS tree in the form of a dictionary where each key is an added edge
    defined as (unit1, unit2, group) and the value is a tuple of the best timetables and
    the strategy tree for every possible next edge
    """
    children = {}
    # add an edge - a group that is shared between two people
    for edge_id, (unit1, unit2, course, course_unit) in enumerate(edges):
        # divide the units' timetables by groups
        timetables_by_groups: dict[int, dict[tt.GroupEntry, list[int]]] = {}
        for unit in (unit1, unit2):
            timetables_by_groups[unit] = defaultdict(list)
            for timetable_id in timetables[unit]:
                group = _find_group_in_timetable(
                    planner_units[unit].ranked_timetables[timetable_id][0], course, course_unit
                )
                timetables_by_groups[unit][group].append(timetable_id)

        for group in planner_units[unit1].groups[course][course_unit]:
            # if there are no timetables left, stop the search
            if not (timetables_by_groups[unit1][group] and timetables_by_groups[unit2][group]):
                break
            # keep the timetables that match the added group edge
            remaining_timetables = timetables.copy()
            best_timetables: dict[int, list[int]] = {}
            for unit in (unit1, unit2):
                remaining_timetables[unit] = timetables_by_groups[unit][group]
                if n:
                    best_timetables[unit] = remaining_timetables[unit][:n]
                else:
                    best_timetables[unit] = remaining_timetables[unit]

            children[(unit1, unit2, group)] = (
                best_timetables,
                _strategy_dfs(n, edges[edge_id + 1:], remaining_timetables, planner_units)
            )
    return children


def get_all_strategies(
        n: int | None,
        planner_units: list[PlannerUnit],
        edges: list[tuple[int, int, str, str]],
        print_num_elems: bool = False) -> None:
    """
    :param n: number of the best timetables to keep for each planner unit (None keeps all)
    Return all strategies for the given shared group graph, where planner units are vertices
    and groups are edges. Every edge is described by course and course unit.
    A strategy is an order in which the shared groups should be added to the timetables.
    No edge does not represent anything. Resulting tree is saved to a json file.
    :param planner_units: list of planner units
    :param edges: the full graph, where an edge represents shared groups between planner units
    in format (1st planner unit id, 2nd planner unit id, course, course_unit),
    where planner unit id is an index in the planner_units list.
    :param print_num_elems: If True, print the number of elements in the resulting strategy tree
    :return: None
    """

    # keep only those edges whose course unit has more than one group
    # (otherwise the course unit will always be shared)
    used_edges = list({(min(unit1, unit2), max(unit1, unit2), course, course_unit)
                       for unit1, unit2, course, course_unit in edges
                       if unit1 != unit2
                       and len(planner_units[unit1].groups[course][course_unit]) > 1})

    all_timetables = {planner_id: list(range(len(planner_unit.ranked_timetables)))
                      for planner_id, planner_unit in enumerate(planner_units)}

    strategy_tree = _strategy_dfs(n, used_edges, all_timetables, planner_units)
    # save the tree to a json
    print("Saving strategy tree to strategy_tree.json")
    with open('strategy_tree.json', 'w', encoding='utf-8') as file:
        file.write(jsonpickle.encode(strategy_tree))

    # get number of all elements (recursively) in the strategy tree
    if print_num_elems:
        def _get_num_elements(tree):
            if not isinstance(tree, dict):
                return 1
            return 1 + sum(_get_num_elements(subtree) for _, subtree in tree.values())
        print("Number of elements in strategy tree:", _get_num_elements(strategy_tree))
