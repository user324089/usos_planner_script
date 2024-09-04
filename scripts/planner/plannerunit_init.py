import pathlib
import usos_tools.courses
import usos_tools.timetables as tt

from .utils import read_personal_config, COURSE_TERMS
from .plannerunit import PlannerUnit
from .timetables import get_top_timetables

def init_planner_unit_from_config(path: pathlib.Path,
                                  session_hash: str, dydactic_cycle: str, cookies) -> PlannerUnit:
    """Creates a planner unit from config files."""
    courses, evaluator = read_personal_config(path)

    # get terms for courses
    for course in courses:
        if course not in COURSE_TERMS:
            COURSE_TERMS[course] = usos_tools.courses.get_course_term(course, dydactic_cycle)

    template_timetable_name = 'automatic_template_' + path.name + '_' + session_hash

    timetable_id = -1
    # do not create a timetable if the session is anonymous
    if cookies:
        # create a timetable with all courses
        timetable_id: int = tt.create_timetable(template_timetable_name, cookies)
        for course in courses:
            tt.add_course_to_timetable(timetable_id, course, COURSE_TERMS[course], cookies)

    groups: dict[str, dict[str, list[tt.GroupEntry]]] = {}
    for course in courses:
        groups.update(usos_tools.courses.get_course_groups(course, COURSE_TERMS[course], False))

    unit = PlannerUnit(
        name=path.name,
        courses=courses,
        evaluator=evaluator,
        template_timetable_id=timetable_id,
        groups=groups,
        config_path=path,
    )
    unit.ranked_timetables = get_top_timetables(unit)
    return unit