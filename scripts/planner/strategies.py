"""
This module contains all function related to finding and evaluating tiemtable strategies.
"""
from collections import defaultdict
from functools import partial
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
        print_num_elems: bool = False) -> dict:
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
    :return: strategy tree
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
        file.write(jsonpickle.encode(strategy_tree, keys=True))

    # get number of all elements (recursively) in the strategy tree
    if print_num_elems:
        def _get_num_elements(tree):
            if not isinstance(tree, dict):
                return 1
            return 1 + sum(_get_num_elements(subtree) for _, subtree in tree.values())
        print("Number of elements in strategy tree:", _get_num_elements(strategy_tree))

    return strategy_tree


def _strategy_eval_power(scores: list[float], n: float = 2) -> float:
    """
    Helper function for strategy evaluation.
    :param scores: scores of the timetables
    :param n: power to raise the sum of scores to
    :return: sum of scores raised to the power of n
    """
    return sum(scores)**n


STRATEGY_EVAL_FUNCTIONS = {
    'power': _strategy_eval_power
}

# set[[score, dict[unit_id, list[timetable_id]]]
# best_strategies: set[[float, dict[str, list[int]]]] = set()
# [score] -> list[strategy]
best_strategies: dict[float, list[dict[int, list[int]]]] = defaultdict(list)


def get_top_strategies(
        n: int | None,
        eval_function_name: str,
        eval_function_args: dict,
        strategy_tree: dict,
        planner_units: list[PlannerUnit]
) -> dict[float, list[dict[int, list[int]]]]:
    """
    Returns the top strategies for the given strategy tree. Score of a strategy is calculated by
    summing scores of all sub-stragies and the score of the current set of timetables.
    :param n: number of strategies to return
    :param eval_function_name: evaluation function to use for timetable tuples
    :param eval_function_args: arguments for the evaluation function
    :param strategy_tree: strategy tree in the form of a dictionary where each key is an added edge
    defined as (unit1, unit2, group) and the value is a tuple of the best timetables and
    the strategy tree for every possible next edge (output of _strategy_dfs)
    :param planner_units: list of planner units
    :return: list of tuples [score, dict[unit_id, list[timetable_id]]]
    representing the best strategies
    """

    best_timetables: dict[int, list[int]] = {}
    for unit_id, planner_unit in enumerate(planner_units):
        best_timetables[unit_id] = list(range(len(planner_unit.ranked_timetables)))

    # create the partial evaluator function with the given arguments
    eval_func = partial(STRATEGY_EVAL_FUNCTIONS[eval_function_name], **eval_function_args)
    _strategy_tree_dfs(n, 1, strategy_tree, eval_func,
                       planner_units, best_timetables, 0)
    return best_strategies


def _strategy_tree_dfs(
        n: int,
        depth: int,
        strategy_tree: dict,
        eval_function: callable,
        planner_units: list[PlannerUnit],
        timetables: dict[int, list[int]],
        score: float,
) -> None:
    """
    Recursive function that evaluates the strategy tree and saves the best strategies.
    :param n: number of the best strategies to keep
    :param strategy_tree: strategy tree in the form of a dictionary where each key is an added edge
    defined as (unit1, unit2, group) and the value is a tuple of the best timetables and
    the strategy tree for every possible next edge (output of _strategy_dfs)
    :param eval_function: evaluation function to use for timetable tuples
    :return: None
    """

    for best_timetables, subtree in strategy_tree.values():
        updated_timetables = timetables.copy()
        for planner_unit_id, timetable_ids in best_timetables.items():
            # move timetables with more groups in common to the front
            try:
                updated_timetables[planner_unit_id].remove(timetable_ids)
            except ValueError:
                pass  # discard timetables
            updated_timetables[planner_unit_id] \
                = timetable_ids + updated_timetables[planner_unit_id]

        # best timetable score for each planner unit
        timetable_scores = [
            planner_units[planner_unit_id].ranked_timetables[timetable_ids[0]][1]
            for planner_unit_id, timetable_ids in updated_timetables.items()
        ]
        # evaluate the current (sub-)strategy
        new_score = (score + eval_function(timetable_scores)) / float(depth)

        # keep only n best strategies
        best_strategies[new_score].append(updated_timetables)
        if len(best_strategies) > n:
            del best_strategies[max(best_strategies.keys())]

        # continue the search
        _strategy_tree_dfs(n, depth+1, subtree, eval_function, planner_units,
                           updated_timetables, new_score)
