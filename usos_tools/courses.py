"""This module contains functions for fetching information about courses from the USOS API."""
import json
from datetime import datetime
from functools import lru_cache
from collections import defaultdict
import pathlib
import jsonpickle
import requests
from usos_tools.utils import (USOSAPI_TIMEOUT, USOSAPI_BASE_URL,
                              ODD_DAYS, EVEN_DAYS, ALL_DAYS, WEEKDAYS_POLISH)
from usos_tools.utils import (_transform_time, _merge_groups_by_time,
                              _is_file_cached, _save_cache, _load_cache)
from usos_tools.models import HourEntry, GroupEntry
import usos_tools.users

FREQUENCY = [ODD_DAYS, EVEN_DAYS]
LOCAL_CACHE_DIR = pathlib.Path('courses')

@lru_cache
def _get_term_weeks(term: str) -> tuple[str, str]:
    """Returns the beginning of odd week and one even week during which all classes take place."""
    if term in {'2024Z', '2024'}:
        return '2024-10-14', '2024-10-07'
    raise ValueError('Term not supported')

def _merge_hour_entries_by_time(group_hours: list[HourEntry] | set[HourEntry]) -> list[HourEntry]:
    """Merges HourEntries with different parities but the same time and day into
    a single HourEntry with ALL_DAYS parity."""
    merged_hours = defaultdict(list)
    for hour in group_hours:
        merged_hours[(hour.day, hour.time_from, hour.time_to)].append(hour)

    result = []
    for hours in merged_hours.values():
        if len(hours) > 1:
            hours[0].parity = ALL_DAYS
        result.append(hours[0])
    return result

def _init_hour_entry_from_json(activity, week_parity: int) -> HourEntry:
    """Initializes a HourEntry object from a JSON object (received from USOS API)."""
    start_date = datetime.strptime(activity['start_time'], '%Y-%m-%d %H:%M:%S')
    end_date = datetime.strptime(activity['end_time'], '%Y-%m-%d %H:%M:%S')
    return HourEntry(
        day=WEEKDAYS_POLISH[start_date.weekday()],
        parity=week_parity,
        time_from=_transform_time(start_date.hour, start_date.minute),
        time_to=_transform_time(end_date.hour, end_date.minute)
    )

def _merge_course_groups_by_time(course_groups: dict[str, dict[str, list[GroupEntry]]]) \
        -> dict[str, dict[str, list[GroupEntry]]]:
    """
    Helper function for get_course_groups.
    Merges groups with the same hours and the same classtype.
    :param course_groups: dict of the form [course][classtype] -> list of GroupEntries
    :return: same dict, but with merged groups
    """
    for _, course_units in course_groups.items():
        for classtype, groups in course_units.items():
            course_units[classtype] = _merge_groups_by_time(groups)
    return course_groups

def get_course_groups(course: str, term: str, merge_groups: bool) \
        -> dict[str, dict[str, list[GroupEntry]]]:
    """
    Fetches all groups for the course in the given term.
    :param course: course id
    :param term: course term (edition)
    :param merge_groups: if True, groups with the same hours will be merged
    :return: dict of the form [course][classtype] -> list of GroupEntries
    """
    if _is_file_cached(LOCAL_CACHE_DIR / f"{course}_{term}.json"):
        course_groups = jsonpickle.decode(_load_cache(LOCAL_CACHE_DIR / f"{course}_{term}.json"))
        if merge_groups:
            course_groups = _merge_course_groups_by_time(course_groups)
        return course_groups

    # [classtype][group_number] -> list of HourEntries for this group
    group_hours: dict[str, dict[str, list[HourEntry]]] = defaultdict(lambda: defaultdict(list))
    # [classtype, group_num] -> lecturer_ids
    group_to_lecturer_ids: dict[tuple[str, str], set[str]] = defaultdict(set)

    for week_start, week_parity in zip(_get_term_weeks(term), FREQUENCY):
        activities_response = requests.get(
            USOSAPI_BASE_URL + '/tt/course_edition',
            params={
                'course_id': course,
                'term_id': term,
                'start': week_start,
                'days': 7,
                'fields': 'classtype_id|group_number|start_time|end_time|lecturer_ids'
            },
            timeout=USOSAPI_TIMEOUT
        )
        activities_response.raise_for_status()

        # extract all class hours and group them by classtype and group number
        activities = activities_response.json()
        for activity in activities:
            group_hours[activity['classtype_id']][activity['group_number']].append(
                _init_hour_entry_from_json(activity, week_parity)
            )
            # add all lecturers to the list, cast as str
            group_to_lecturer_ids[(activity['classtype_id'], activity['group_number'])].update(
                str(lecturer_id) for lecturer_id in activity['lecturer_ids']
            )

    # ids of all lecturers in the course
    lecturer_ids = list({str(lecturer_id) for lecturer_ids in group_to_lecturer_ids.values()
                    for lecturer_id in lecturer_ids})
    # get all lecturers' names
    lecturers = defaultdict(lambda: ('-', '-'))
    lecturers.update(usos_tools.users.get_course_lecturers(course, term, lecturer_ids))

    groups: dict[str, list[GroupEntry]] = defaultdict(list)
    for classtype, groups_info in group_hours.items():
        for number, hours in groups_info.items():
            groups[classtype].append(
                GroupEntry(
                    group_nums={str(number)},
                    course=course,
                    classtype=classtype,
                    hours=set(_merge_hour_entries_by_time(hours)),
                    teacher=', '.join(
                        f"{lecturers[lecturer_id][0]} {lecturers[lecturer_id][1]}"
                        for lecturer_id in group_to_lecturer_ids[(classtype, number)]
                    )
                )
            )

    course_groups = {course: groups}
    # cache the result
    _save_cache(LOCAL_CACHE_DIR / f"{course}_{term}.json", jsonpickle.encode(course_groups))

    if merge_groups:
        course_groups = _merge_course_groups_by_time(course_groups)
    return course_groups

@lru_cache
def get_course_term(course: str, term: str) -> str:
    """
    Returns the term which is the best match from the course's terms.
    :param course: course id
    :param term: term id (course edition)
    :return: term id
    """
    terms_cache_file = pathlib.Path(f'{course}_terms.json')
    # try to get course terms from cache
    if _is_file_cached(LOCAL_CACHE_DIR / terms_cache_file):
        terms = json.loads(_load_cache(LOCAL_CACHE_DIR / terms_cache_file))
    else:
        response = requests.get(
            USOSAPI_BASE_URL + '/courses/course',
            params={
                'course_id': course,
                'fields': 'terms'
            },
            timeout=USOSAPI_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        terms = [term_data['id'] for term_data in data['terms']]
        _save_cache(LOCAL_CACHE_DIR / terms_cache_file, json.dumps(terms))

    best_match = None
    year = term[:4]

    for course_term in terms:
        if course_term == term:
            return course_term
        if course_term == year:
            best_match = course_term

    if best_match is None:
        raise RuntimeError(f"Failed to find matching term for course {course}.")
    return best_match
