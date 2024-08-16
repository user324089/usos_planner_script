"""This module provides functionality to manipulate timetables in USOSweb."""
import re
import typing
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import bs4
import matplotlib.pyplot as plt
from usos_tools.utils import (USOSWEB_KONTROLER_BASE_URL, DEFAULT_TIMEOUT,
                              ODD_DAYS, EVEN_DAYS, ALL_DAYS, WEEKDAYS_POLISH)
from usos_tools.utils import (_create_form_str, _get_csrf_token, _get_weekday_polish,
                              _get_parity_polish, _parity_to_int_polish, _get_classtype_polish,
                              _transform_time, _merge_groups_by_time, do_groups_collide)
from usos_tools.models import HourEntry, GroupEntry


def add_course_to_timetable(timetable_id: int, course_id: str, dydactic_cycle: str, cookies):
    """Adds the course (all groups) to the timetable."""
    requests.get(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/dodajWpis',
            'plan_id': timetable_id,
            'klasa': 'P',
            'prz_kod': course_id,
            'cdyd_kod': dydactic_cycle
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def create_timetable (name: str, cookies) -> int:
    """Creates an empty timetable in USOS and returns its id."""
    create_request = requests.get (
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/utworz',
            'nazwa': name
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    print ('created timetable:', name)
    return re.findall (r'plan_id=(\d*)', create_request.url)[0]

def rename_timetable (timetable_id: int, new_name: str, cookies):
    """Changes timetable's name to new_name."""
    edit_request = requests.get(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/edytuj',
            'plan_id': timetable_id
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    csrftoken: str = _get_csrf_token(edit_request.text)
    payload, boundary = _create_form_str({
        '_action': 'home/plany/zmienNazwe',
        'plan_id': str(timetable_id),
        'csrftoken': csrftoken,
        'nazwa': new_name
    })
    requests.post(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/zmienNazwe',
            'plan_id': timetable_id
        },
        data=payload,
        headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def copy_timetable (timetable_id: int, cookies):
    """Creates a copy of a timetable."""
    requests.get(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/skopiuj',
            'plan_id': timetable_id
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def duplicate_timetable (timetable_id: int, num: int, name: str, cookies) -> list[int]:
    """Duplicates the timetable with given timetable_id num times, numbers the duplicates
    and returns their ids."""
    previous_timetables_ids: set[int] = set(
        timetable_id for _, timetable_id in get_all_timetables(cookies)
    )
    for _ in range (num):
        copy_timetable(timetable_id, cookies)
    # get all timetables (now including the copies)
    current_timetables_ids: list[int] = [
        timetable_id for _, timetable_id in get_all_timetables(cookies)
    ]
    # ids of the copies
    new_timetables_ids = [
        timetable_id for timetable_id in current_timetables_ids
        if timetable_id not in previous_timetables_ids
    ]
    # rename the copies
    for current_index, changed_timetable_id in enumerate(new_timetables_ids):
        rename_timetable(changed_timetable_id, name + ' ' + str(current_index), cookies)
        print ('duplicated timetable ', current_index)

    return new_timetables_ids

def _get_entry_data (entry: bs4.element.Tag):
    """Retrieves info about a single timetable entry."""
    name = entry.find_all('div')[0].string
    dates = ''
    i: bs4.element.Tag
    for i in entry.find_all('span'):
        if i.string is None:
            continue
        if re.search (r'\d*:\d*', i.string):
            dates = i.string

    name_match = typing.cast(re.Match[str], re.search (r'^([A-Z]*),\s*gr\.\s*(\d*)', name))
    time_match = typing.cast(re.Match[str], re.search(r'(\d*):(\d*) - (\d*):(\d*)', dates))

    person_div = entry.find ('div', {'slot': 'dialog-person'})
    teacher: str = 'UNKNOWN'
    if person_div is not None:
        teacher = person_div.text.strip().replace (',', '')

    data = {
        'classtype': name_match.group(1),
        'group_num': name_match.group(2),
        'day': _get_weekday_polish(dates),
        'parity': _parity_to_int_polish(_get_parity_polish(dates)),
        'course': entry['name-id'],
        'time_from': _transform_time (time_match.group(1), time_match.group(2)),
        'time_to': _transform_time (time_match.group(3), time_match.group(4)),
        'teacher': teacher
    }
    return data

def split_course(timetable_id: int, n: int, groups: dict[str, GroupEntry], cookies):
    """Split n-th unsplit course entry in the timetable, keeping only given groups.
    Groups must be sorted by classtype into lists."""
    # groups: [classtype, GroupEntry]
    split_list_request = requests.get(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/rozbijWpis',
            'plan_id': timetable_id,
            'nr': n
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    split_list_soup = BeautifulSoup(split_list_request.content, 'html.parser')
    # remaining groups
    remaining_indices: list[int] = []
    for current_index, tr in enumerate(split_list_soup.find_all('tr')):
        tr_spans: list[bs4.Tag] = tr.find_all('span')
        if len(tr_spans) < 2:
            continue
        tr_span: bs4.Tag = tr_spans[-1]

        classtype: str = _get_classtype_polish(tr_span.contents[0].text)

        if (group_num_match := re.search(r'grupa nr (\d*)', tr_span.contents[1].text)) is None:
            raise TypeError("Group number not found.")
        group_num = group_num_match.group(1)

        if group_num in groups[classtype].group_nums:
            remaining_indices.append(current_index - 1)

    form_dict: dict[str, str] = {
        '_action': 'home/plany/rozbijWpis',
        'plan_id': str(timetable_id),
        'nr': str(n),
        'zapisz': '1',
        'csrftoken': _get_csrf_token(split_list_request.text)
    }
    form_dict.update({'entry' + str(on_index): 'on' for on_index in remaining_indices})

    payload, boundary = _create_form_str(form_dict)
    requests.post(
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/rozbijWpis',
            'plan_id': timetable_id
        },
        data=payload,
        headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def split_timetable (timetable_id: int, groups: dict[tuple[str, str], GroupEntry], cookies):
    """Create a timetable containing given groups
    by splitting a preexisting timetable given by timetable_id."""
    # groups: [[course, classtype], groups]

    edit_request = requests.get (
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/edytuj',
            'plan_id': timetable_id
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    edit_soup = BeautifulSoup (edit_request.content, 'html.parser')

    # course units appearing in the timetable
    split_courses: list[str] = []
    for tr in edit_soup.find_all ('tr'):
        if span := tr.find('span'):
            split_courses.extend(span.contents)

    groups_to_keep_by_course = defaultdict(lambda: defaultdict(GroupEntry))
    for (course, classtype), group in groups.items():
        groups_to_keep_by_course[course][classtype] = group

    # iterating through all the courses in the timetable
    for course in split_courses:
        split_course(timetable_id, 0, groups_to_keep_by_course[course], cookies)

def get_groups_from_timetable (timetable_id: int, merge_groups: bool,
                               cookies)  -> dict[str, dict[str, list[GroupEntry]]]:
    """Returns all groups from the timetable with given id.
    If merge_groups is True, groups with the same hours are merged.
    Groups are grouped by course name and classtype. """

    timetable_page = requests.get (
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/pokaz',
            'plan_id': timetable_id,
            'plan_division': 'semester'
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

    print ('downloaded timetable')

    whole_timetable_soup = BeautifulSoup (timetable_page.content, 'html.parser')
    all_timetable_entries = whole_timetable_soup.find_all ('timetable-entry')
    all_timetable_entries_data = [_get_entry_data(i) for i in all_timetable_entries]

    tt_entries_by_course_unit = defaultdict(list)
    for data in all_timetable_entries_data:
        tt_entries_by_course_unit[(data['course'], data['classtype'])].append(data)

    # all groups, grouped in lists by their course units
    all_groups: dict[str, dict[str, list[GroupEntry]]] = defaultdict(lambda: defaultdict(list))

    for course_unit, timetable_entries in tt_entries_by_course_unit.items():
        # [group number : GroupEntry] - groups belonging to the current course unit
        course_name = course_unit[0]
        course_type = course_unit[1]
        current_groups: dict [str, GroupEntry] = {}

        for timetable_entry in timetable_entries:
            group_num = timetable_entry['group_num']
            if group_num not in current_groups:
                current_groups[group_num] = GroupEntry(
                    group_nums = {group_num},
                    course = course_name,
                    classtype = course_type
                )

            current_hour = HourEntry(
                day = timetable_entry['day'],
                parity = timetable_entry['parity'],
                time_from = timetable_entry['time_from'],
                time_to = timetable_entry['time_to']
            )
            current_groups[group_num].hours.add(current_hour)
            current_groups[group_num].teacher = timetable_entry['teacher']

        group_list = list(current_groups.values())
        if merge_groups:
            group_list = _merge_groups_by_time(group_list)

        all_groups[course_name][course_type] = group_list

    return all_groups

def get_all_timetables (cookies) -> list[tuple[str, int]]:
    """Returns a list of all timetables, consisting of (name, id) tuples."""
    r = requests.get (
        USOSWEB_KONTROLER_BASE_URL,
        params={'_action': 'home/plany/index'},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    soup = BeautifulSoup (r.content, 'html.parser')
    timetables: list [tuple[str, int]] = []
    for tr in soup.find_all ('tr')[:-1]:
        td: bs4.element.Tag = tr.find ('td')
        timetable_name = td.text.strip()
        dropdown: bs4.element.Tag = tr.find ('dropdown-menu')
        dropdown_data_timetable_id: str | list[str] = dropdown['data-plan-id']
        dropdown_timetable_id = int(str(dropdown_data_timetable_id))
        timetables.append ((timetable_name, dropdown_timetable_id))
    return timetables

def delete_timetable (timetable_id: int, cookies):
    """Deletes the timetable with given id."""
    requests.get (
        USOSWEB_KONTROLER_BASE_URL,
        params={
            '_action': 'home/plany/usun',
            'plan_id': timetable_id
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def display_timetable(groups: list[GroupEntry], name: str):
    """Shows the timetable as a plot."""
    fig, ax = plt.subplots()

    ax.set_xticks(range(len(WEEKDAYS_POLISH)))
    ax.set_xticklabels(WEEKDAYS_POLISH)

    ax.set_yticks(range(7, 21))
    ax.set_yticklabels([f'{h}:00' for h in range(7, 21)])
    ax.invert_yaxis()

    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # assign a color to each course
    course_to_color = {group.course: i for i, group in enumerate(groups)}
    colors = plt.get_cmap('tab20')(range(len(groups)))

    for group in groups:
        for hour in group.hours:
            start, end = hour.time_from, hour.time_to
            day_index = WEEKDAYS_POLISH.index(hour.day)

            height = end - start
            width = 1 if hour.parity == ALL_DAYS else 0.5
            x_middle = day_index
            if hour.parity == ODD_DAYS:
                x_middle += width/2
            elif hour.parity == EVEN_DAYS:
                x_middle -= width/2

            ax.bar(x_middle, height, bottom=start, width=width, edgecolor='black',
                   color=colors[course_to_color[group.course]], align='center')
            info = f'{group.course} {group.classtype} {", ".join(group.group_nums)}'
            ax.text(x_middle, (start + end) / 2, info,
                    va='center', ha='center', fontsize=10, color='black')

    ax.set_xlabel('Days')
    ax.set_ylabel('Time')

    plt.title(name)
    plt.show()

class TmpTimetable:
    """Class for creating a temporary timetable. Can be used in a "with ... as" statement."""
    timetable_id: int

    def __init__(self, cookies):
        self.cookies = cookies

    def __enter__(self):
        self.timetable_id = create_timetable ('', self.cookies)
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        # TODO handle exceptions
        delete_timetable (self.timetable_id, self.cookies)
