"""Module that calculates the best possible timetables containing given courses
using a given evaluator function, then creates them in USOS."""
import random
from getpass import getpass
import sys
import pathlib
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import json
import argparse
import math
import requests
import usos_tools.login
import usos_tools.timetables as tt
from usos_tools.utils import EVEN_DAYS, ODD_DAYS

NUM_TIMETABLES = 1
USOSAPI_TIMEOUT = 5

COURSE_TERMS: dict[str, str] = {}

def get_course_term(course: str, term: str) -> str:
    """Returns the course term that is the best match for the given term."""
    response = requests.get(
        "https://usosapps.uw.edu.pl/services/courses/course",
        params={"course_id": course, "fields": "terms"},
        timeout=USOSAPI_TIMEOUT
    )
    response.raise_for_status()
    data = response.json()

    best_match = None
    year = term[:4]

    for term_data in data["terms"]:
        course_term = term_data["id"]

        if course_term == term:
            return course_term
        if course_term == year:
            best_match = course_term

    if best_match is None:
        raise RuntimeError(f"Failed to find matching term for course {course}.")
    return best_match


def read_words_from_file (filename: str) -> list[str]:
    """Returns a list of all words in the file."""
    try:
        with open (filename, 'r', encoding="utf-8") as f:
            return f.read().split()
    except FileNotFoundError:
        return []

def evaluate_timetable_time (timetable: list[tt.GroupEntry], _: pathlib.Path) -> int:
    """Returns timetable badness with regard to the days' length, their start and end."""
    # mapping hours of all classes taking place at a given day to that day
    map_days_to_hours: dict[tuple[str, int], list[tt.HourEntry]] = defaultdict(list[tt.HourEntry])

    for entry in timetable:
        for hour in entry.hours:
            if hour.parity & EVEN_DAYS:
                map_days_to_hours[(hour.day, EVEN_DAYS)].append(hour)
            if hour.parity & ODD_DAYS:
                map_days_to_hours[(hour.day, ODD_DAYS)].append(hour)


    day_lens: list[tuple[int,int]] = []
    for current_hour_list in map_days_to_hours.values():
        to = max (hour.time_to for hour in current_hour_list)
        fro = min (hour.time_from for hour in current_hour_list)
        day_lens.append ((fro, to))

    res = 0
    for l in day_lens:
        res += 20
        res += l[1]-l[0]
        if l[0] < 10:
            res += 2
        if l[1] > 15:
            res += 2
        if l[1] > 17:
            res += 10
        if l[1] - l[0] > 9:
            res += 30
    return res

custom_evaluate_data = {}
def evaluate_timetable_custom (timetable: list[tt.GroupEntry], path: pathlib.Path) -> int:
    """Returns timetable badness as a sum of badnesses of each group in it."""
    if path in custom_evaluate_data:
        data = custom_evaluate_data[path]
    else:
        with open ((path / 'data.json').resolve(), 'r', encoding="utf-8") as data_file:
            data = json.load(data_file)
            custom_evaluate_data[path] = data
    result: int = 0
    for group in timetable:
        values_for_groups = [int(data[group.course][group.classtype][single_group])
                             for single_group in group.group_nums]
        result += min(values_for_groups)

    return result


EVALUATORS = {
    'time': evaluate_timetable_time,
    'custom': evaluate_timetable_custom
}

def list_possible_timetables (all_course_units: dict[str, dict[str, list[tt.GroupEntry]]]):
    """Returns a list of all timetables with non-colliding groups."""
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

@dataclass
class PlannerUnit:
    """Class representing a timetable optimizer."""
    name: str = 'unnamed'
    evaluator: str = 'time'
    # all attended courses
    courses: set[str] = field(default_factory=set)
    # all groups from all attended courses, sorted by course,
    # then by course unit they belong to
    # map from course code and type to groups
    groups: dict[str, dict[str, list[tt.GroupEntry]]] = field(default_factory=dict)
    config_path: pathlib.Path = field(default_factory=pathlib.Path)

    ranked_timetables: list[tuple[list[tt.GroupEntry], float]] = field(default_factory=list)

    template_timetable_id: int = -1

    def __str__ (self):
        return 'name: ' + self.name + ' evaluator: ' + self.evaluator

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


def init_planner_unit_from_config(path: pathlib.Path,
                                  session_hash: str, dydactic_cycle: str, cookies) -> PlannerUnit:
    """Creates a planner unit from config files."""
    courses, evaluator = read_personal_config(path)

    # get terms for courses
    for course in courses:
        if course not in COURSE_TERMS:
            COURSE_TERMS[course] = get_course_term(course, dydactic_cycle)

    template_timetable_name = 'automatic_template_' + path.name + '_' + session_hash
    # create a timetable with all courses
    timetable_id: int = tt.create_timetable(template_timetable_name, cookies)
    for course in courses:
        tt.add_course_to_timetable(timetable_id, course, COURSE_TERMS[course], cookies)

    return PlannerUnit(
        name = path.name,
        courses = courses,
        evaluator = evaluator,
        template_timetable_id= timetable_id,
        groups = tt.get_groups_from_timetable(timetable_id, True, cookies),
        config_path = path
    )


def min_normalize (values: list[int]) -> list[float]:
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
    timetable_scores = min_normalize(timetable_scores)
    timetables_with_scores = list(zip(possible_timetables, timetable_scores))

    # sort timetables by badness
    timetables_with_scores.sort(key=lambda x: x[1])

    # return top n
    if n is None:
        return timetables_with_scores
    return timetables_with_scores[:n]


def groups_fit (subset: list[tt.GroupEntry], superset: list[tt.GroupEntry]) -> bool:
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
            NUM_TIMETABLES
        )
        # list of timetables for any person should have at least n entries
        if len(individual_timetables) < n:
            return [], math.inf
        # update the group timetables/score
        best_timetables_per_person.append(individual_timetables)
        group_score += individual_score ** 3

    return best_timetables_per_person, group_score

def get_shared_courses (planner_units: list[PlannerUnit]) -> list[str]:
    """Returns a set of courses that are attended by more than one person."""
    # count the number of occurrences of each course using Counter
    course_counter = Counter(
        course for planner_unit in planner_units for course in planner_unit.courses
    )
    return [course for course, count in course_counter.items() if count > 1]


def get_login_credentials() -> tuple[str, str]:
    """Gets login credentials from a file or from the user."""
    parser = argparse.ArgumentParser(description='Usos planner')
    parser.add_argument('-l', '--login', metavar='FILE', help='Usos login data file')
    args = parser.parse_args()
    if args.login:
        login_filename = args.login
        with open (login_filename, 'r', encoding="utf-8") as login_file:
            credentials = login_file.read().split('\n')
            if len(credentials) < 2:
                raise RuntimeError('Failed to read credentials')
            username = credentials[0]
            password = credentials[1]
    else:
        username = input('username:')
        password = getpass()
    return username, password


def main() -> int:
    """Calculates the best possible timetables according to config and creates them in USOS."""
    dydactic_cycle: str = read_dydactic_cycle()

    current_hash = ''.join(random.choices('ABCDEFGH', k=6))
    print ('starting run:', current_hash)

    php_session_cookies = usos_tools.login.log_in_to_usos(*get_login_credentials())

    all_planner_units: list[PlannerUnit] = []

    config_directory: pathlib.Path = pathlib.Path ('./config')
    personal_configs = [directory for directory
                        in config_directory.iterdir() if directory.is_dir()]

    for personal_config in personal_configs:

        current_unit: PlannerUnit = init_planner_unit_from_config(
            personal_config,
            current_hash,
            dydactic_cycle,
            php_session_cookies
        )
        current_unit.ranked_timetables = get_top_timetables(current_unit)
        print(current_unit)
        all_planner_units.append(current_unit)

    # get all courses that are attended by more than one person
    shared_courses = get_shared_courses(all_planner_units)

    # find all possible timetables with duplicate courses. this approach does not scale,
    # but for at most 3 people it is enough
    with tt.TmpTimetable(php_session_cookies) as shared_timetable:
        # create a timetable containing only shared courses
        for shared_course in shared_courses:
            tt.add_course_to_timetable(
                shared_timetable.timetable_id,
                shared_course,
                COURSE_TERMS[shared_course],
                php_session_cookies
            )
        shared_groups = tt.get_groups_from_timetable(
            shared_timetable.timetable_id, True, php_session_cookies
        )
        shared_groups_timetables = list_possible_timetables (shared_groups)

    # list of timetables that fit a certain shared timetable for all people
    best_matching_timetables: list[list[int]] = []
    # best attained combined score (we attempt to minimize it)
    best_group_score: float = math.inf

    for shared_timetable in shared_groups_timetables:
        best_timetables_per_person, group_score = get_best_fitting_timetables_group(
            all_planner_units,
            shared_timetable,
            NUM_TIMETABLES
        )
        # update if set of timetables is better
        if group_score < best_group_score:
            best_group_score = group_score
            best_matching_timetables = best_timetables_per_person

    if len(best_matching_timetables) == 0:
        print ('failed to find a timetable system')
        return 1


    for index, current_unit in enumerate(all_planner_units):
        top_timetables = [current_unit.ranked_timetables[i]
                          for i in best_matching_timetables[index][:NUM_TIMETABLES]]
        # ids of copies of the original timetable
        timetable_instance_ids: list[int] = (
            tt.duplicate_timetable(
                current_unit.template_timetable_id,
                len(top_timetables),
                'automatic_instance_' + current_unit.name + '_' + current_hash + '__',
                php_session_cookies
            )
        )

        # recreate the top timetables in USOS
        for (timetable, _), timetable_id in zip(top_timetables, timetable_instance_ids):

            course_unit_to_groups: dict[tuple[str, str], tt.GroupEntry] = {
                (group.course, group.classtype) : group for group in timetable
            }
            tt.split_timetable (timetable_id, course_unit_to_groups, php_session_cookies)
            print ('shattered timetable')
    return 0

if __name__ == '__main__':
    sys.exit(main())
