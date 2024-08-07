"""Module that calculates the best possible timetables containing given courses
using a given evaluator function, then creates them in USOS."""
import random
from getpass import getpass
import sys
import pathlib
from collections import defaultdict
from dataclasses import dataclass, field
import json
import argparse
import requests
import usos_tools.login
import usos_tools.timetables as tt
from usos_tools.utils import EVEN_DAYS, ODD_DAYS
import math

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

    ranked_plans: list[tuple[list[tt.GroupEntry], float]] = field(default_factory=list)

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

    merge_groups = evaluator != 'custom'
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
        groups = tt.get_groups_from_timetable(timetable_id, merge_groups, cookies),
        config_path = path
    )

def get_top_timetables(planner_unit: PlannerUnit, n: int | None = None) -> list[tuple[list[tt.GroupEntry], float]]:
    """Returns top n timetables with scores for a given planner unit."""
    possible_timetables = list_possible_timetables(planner_unit.groups)

    if len(possible_timetables) == 0:
        return []

    best_plan_value = min (EVALUATORS[planner_unit.evaluator](timetable, planner_unit.config_path) for timetable in possible_timetables)
    timetables_with_values: list[tuple[list[tt.GroupEntry], float]] = [
        (timetable, EVALUATORS[planner_unit.evaluator](timetable, planner_unit.config_path) / best_plan_value)
        for timetable in possible_timetables
    ]
    # sort timetables by badness, return top n

    if n is None:
        return sorted(timetables_with_values, key=lambda x: x[1])
    else:
        return sorted(timetables_with_values, key=lambda x: x[1])[:n]

def groups_fit (subset: list[tt.GroupEntry], superset: list[tt.GroupEntry]) -> bool:
    mp: dict[tuple[str, str], tt.GroupEntry] = {}
    for superset_entry in superset:
        mp[(superset_entry.course, superset_entry.classtype)] = superset_entry
    for subset_entry in subset:
        key: tuple[str, str] = (subset_entry.course, subset_entry.classtype)
        if key in mp and mp[key] != subset_entry:
            return False
    return True

def main() -> int:
    """Calculates the best possible timetables according to config and creates them in USOS."""
    dydactic_cycle: str = read_dydactic_cycle()

    current_hash = ''.join(random.choices('ABCDEFGH', k=6))
    print ('starting run:', current_hash)


    parser = argparse.ArgumentParser(description='Usos planner')
    parser.add_argument('-l', '--login', metavar='FILE', help='Usos login data file')
    args = parser.parse_args()
    if args.login:
        login_filename = args.login
        with open (login_filename, 'r', encoding="utf-8") as login_file:
            credentials = login_file.read().split('\n')
            if len(credentials) < 2:
                print ('Failed to read credentials')
                return 1
            username = credentials[0]
            password = credentials[1]
    else:
        username = input('username:')
        password = getpass()


    php_session_cookies = usos_tools.login.log_in_to_usos (username, password)

    all_planner_units: list[PlannerUnit] = []

    config_directory: pathlib.Path = pathlib.Path ('./config')
    personal_configs = [directory for directory
                        in config_directory.iterdir() if directory.is_dir()]

    # counts the number of occurrences of each subject. is used to find subjects
    # that are attended by more than one person
    map_course_to_number_of_occurences: dict[str, int] = defaultdict(int)

    for personal_config in personal_configs:
        current_unit: PlannerUnit = init_planner_unit_from_config(
            personal_config,
            current_hash,
            dydactic_cycle,
            php_session_cookies
        )
        print(current_unit)
        all_planner_units.append(current_unit)
        for course_name in current_unit.courses:
            map_course_to_number_of_occurences[course_name] += 1

    # is a list of course names that are attended by more than one person
    duplicated_courses = [course_name
                          for course_name, num_occurences in map_course_to_number_of_occurences.items()
                          if num_occurences > 1]

    # find all possible timetables with duplicate courses. this approach does not scale,
    # but for at most 3 people it is enough
    with tt.tmpTimetable(php_session_cookies) as duplicated_timetable:
        for duplicated_course in duplicated_courses:
            tt.add_course_to_timetable (duplicated_timetable.timetable_id, duplicated_course, dydactic_cycle, php_session_cookies)
        duplicate_groups = tt.get_groups_from_timetable (duplicated_timetable.timetable_id, True, php_session_cookies)
        duplicate_timetables = list_possible_timetables (duplicate_groups)

    # rank plans for all people
    for current_unit in all_planner_units:
        current_unit.ranked_plans = get_top_timetables(current_unit)

    #
    best_picked_plans: list[list[int]] = []
    # best attained combined score
    best_score: float = math.inf

    for duplicate_timetable in duplicate_timetables:

        # list of indices of best plans that fit duplicate timetable for all people
        I_picked_plans: list[list[int]] = []
        I_score: float = 0

        # loop finds a plan which fits the duplicates
        for current_unit in all_planner_units:

            # list of indices of best plans that fit duplicate timetable for current person
            II_picked_plans: list[int] = []
            II_score: float = 0

            # loop over all plans in order from best to worst and remember the best NUM_TIMETABLES ones
            for index, (unit_timetable, score) in enumerate(current_unit.ranked_plans):
                if groups_fit (duplicate_timetable, unit_timetable):

                    II_score += score
                    II_picked_plans.append (index)

                    if len(II_picked_plans) == NUM_TIMETABLES:
                        break

            # remember plans of current person
            I_picked_plans.append (II_picked_plans)
            # update the all people score by local score
            I_score += II_score ** 3

        # list of plans for any person should have at least NUM_TIMETABLES entries
        if any (len(try_picked_plan) < NUM_TIMETABLES for try_picked_plan in I_picked_plans):
            continue

        # update if set of plans is better
        if (I_score < best_score):
            best_score = I_score
            best_picked_plans = I_picked_plans


    if len(best_picked_plans) == 0:
        print ('failed to find a plan system')
        return 1

    # get course ids

    for index, current_unit in enumerate(all_planner_units):
        #top_timetables = get_top_timetables(current_unit, NUM_TIMETABLES)
        top_timetables = [current_unit.ranked_plans[i] for i in best_picked_plans[index][:NUM_TIMETABLES]]
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
