"""Module that calculates the best possible timetables containing given courses
using a given evaluator function, then creates them in USOS."""
import random
import pathlib
from collections import Counter
import requests.cookies
import usos_tools.login
import usos_tools.cart
import usos_tools.courses
from scripts.utils import get_login_credentials

from .utils import read_dydactic_cycle
from .plannerunit_init import init_planner_unit_from_config
from .strategies import get_all_strategies
from .plannerunit import PlannerUnit

USOSAPI_TIMEOUT = 5
NUM_TIMETABLES = 1


def get_shared_courses(planner_units: list[PlannerUnit]) -> list[str]:
    """Returns a set of courses that are attended by more than one person."""
    # count the number of occurrences of each course using Counter
    course_counter = Counter(
        course for planner_unit in planner_units for course in planner_unit.courses
    )
    return [course for course, count in course_counter.items() if count > 1]


def initialize(args) -> tuple[requests.cookies.RequestsCookieJar, list[PlannerUnit]]:
    """
    Initializes the planner.
    :param args: command line arguments
    :return: dydactic cycle, current hash, php session cookies, planner units
    """
    dydactic_cycle: str = read_dydactic_cycle()

    current_hash = ''.join(random.choices('ABCDEFGH', k=6))
    print('Starting run:', current_hash)

    # for anonymous session, the cookies are None
    php_session_cookies = None
    if credentials := get_login_credentials(args):
        php_session_cookies = usos_tools.login.log_in_to_usos(*credentials)

    all_planner_units: list[PlannerUnit] = []

    config_directory: pathlib.Path = pathlib.Path('./config')
    personal_configs = [directory for directory
                        in config_directory.iterdir() if directory.is_dir()]

    for personal_config in personal_configs:
        current_unit: PlannerUnit = init_planner_unit_from_config(
            personal_config,
            current_hash,
            dydactic_cycle,
            php_session_cookies
        )
        print(current_unit)
        all_planner_units.append(current_unit)

    return php_session_cookies, all_planner_units


def main(args) -> int:
    """Calculates the best possible timetables according to config and creates them in USOS."""
    php_session_cookies, all_planner_units = initialize(args)

    # create a graph with all edges
    # iterate over all distinct pairs of planner units
    edges: list[tuple[int, int, str, str]] = []
    for i, planner_unit1 in enumerate(all_planner_units):
        for j, planner_unit2 in enumerate(all_planner_units):
            if i >= j:
                continue
            shared_courses = planner_unit1.courses & planner_unit2.courses
            for course in shared_courses:
                for course_unit in planner_unit1.groups[course]:
                    edges.append((i, j, course, course_unit))

    get_all_strategies(NUM_TIMETABLES, all_planner_units, edges, print_num_elems=True)
    return 0
