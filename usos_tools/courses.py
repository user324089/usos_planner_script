"""This module contains functions for fetching information about courses from the USOS API."""
from datetime import datetime
from functools import lru_cache
from collections import defaultdict
import jsonpickle
import requests
from usos_tools.utils import DEFAULT_TIMEOUT, ODD_DAYS, EVEN_DAYS, ALL_DAYS
from usos_tools.utils import (_transform_time, _merge_groups_by_time,
                              _is_file_cached, _save_cache, _load_cache)
from usos_tools.models import HourEntry, GroupEntry

WEEKDAYS_POLISH = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela']
FREQUENCY = {0: ODD_DAYS, 1: EVEN_DAYS}

LOCAL_CACHE_DIR = 'courses'
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

def get_course_groups(course: str, term: str) -> dict[str, dict[str, list[GroupEntry]]]:
    """Returs a dictionary of all groups in a course, grouped by classtype."""
    if _is_file_cached(f"courses/{course}_{term}.json"):
        return jsonpickle.decode(_load_cache(f"courses/{course}_{term}.json"))

    weeks = _get_term_weeks(term)
    # [classtype][group_number] -> list of HourEntries for this group
    group_hours: dict[str, dict[str, list[HourEntry]]] = defaultdict(lambda: defaultdict(list))

    for index, week in enumerate(weeks):
        week_parity = FREQUENCY[index]
        activities_response = requests.get(
            'https://usosapps.uw.edu.pl/services/tt/course_edition',
            params={
                'course_id': course,
                'term_id': term,
                'start': week,
                'days': 7,
                'fields': 'classtype_id|group_number|start_time|end_time'
            },
            timeout=DEFAULT_TIMEOUT
        )
        activities_response.raise_for_status()

        # extract all class hours and group them by classtype and group number
        activities = activities_response.json()
        for activity in activities:
            group_hours[activity['classtype_id']][activity['group_number']].append(
                _init_hour_entry_from_json(activity, week_parity)
            )

    groups: dict[str, list[GroupEntry]] = defaultdict(list)
    for classtype, groups_info in group_hours.items():
        for number, hours in groups_info.items():
            groups[classtype].append(
                GroupEntry(
                    group_nums={number},
                    course=course,
                    classtype=classtype,
                    hours=set(_merge_hour_entries_by_time(hours))
                )
            )
        groups[classtype] = _merge_groups_by_time(groups[classtype])

    course_groups = {course: groups}
    # cache the result
    _save_cache(LOCAL_CACHE_DIR, f"{course}_{term}.json", jsonpickle.encode(course_groups))
    return course_groups
