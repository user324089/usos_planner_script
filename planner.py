"""Module that calculates the best possible timetables containing given courses
using a given evaluator function, then creates them in USOS."""
import re
import typing
import random
from getpass import getpass
import sys
import pathlib
from collections import defaultdict
from dataclasses import dataclass, field
import json
import requests
from bs4 import BeautifulSoup
import bs4

NUM_TIMETABLES = 3
USOSWEB_KONTROLER = 'https://usosweb.mimuw.edu.pl/kontroler.php'
DEFAULT_TIMEOUT = 10

def read_words_from_file (filename: str) -> list[str]:
    """Returns a list of all words in the file."""
    try:
        with open (filename, 'r', encoding="utf-8") as f:
            return f.read().split()
    except FileNotFoundError:
        return []

def log_in_to_usos (username, password):
    """Logs into USOS and returns cookies with PHP session."""

    r1 = requests.get('https://logowanie.uw.edu.pl/cas/login', timeout=DEFAULT_TIMEOUT)
    cookies = r1.cookies

    lt = re.findall ('name="lt" value="(.*?)"', r1.text)[0]
    execution = re.findall ('name="execution" value="(.*?)"', r1.text)[0]
    event_id = re.findall ('name="_eventId" value="(.*?)"', r1.text)[0]

    r2 = requests.post(
        'https://logowanie.uw.edu.pl/cas/login',
        data= {'lt': lt, 'execution': execution, '_eventId': event_id,
               'username': username, 'password': password, 'jsessionid': r1.cookies['JSESSIONID']},
        cookies=r1.cookies,
        timeout=DEFAULT_TIMEOUT
    )
    cookies.update(r2.cookies)

    r3 = requests.get(
        'https://logowanie.uw.edu.pl/cas/login',
        params={'service': USOSWEB_KONTROLER + '?_action=news/default', 'gateway': 'true'},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    print ('logged in to usos')
    return r3.cookies

def add_course_to_timetable(timetable_id: int, course_id: str, dydactic_cycle: str, cookies):
    """Adds the course (all groups) to the timetable."""
    requests.get(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/dodajWpis', 'plan_id': timetable_id,
                'klasa': 'P', 'prz_kod': course_id, 'cdyd_kod': dydactic_cycle},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def create_timetable (name: str, cookies) -> int:
    """Creates an empty timetable in USOS and returns its id."""
    create_request = requests.get (
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/utworz', 'nazwa': name},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    print ('created timetable:', name)
    return re.findall (r'plan_id=(\d*)', create_request.url)[0]

def create_form_str (options: dict[str, str]) -> tuple[str, str]:
    """Creates a multiform post payload and returns it and the boundary."""
    boundary: str = '-' * 27 +  ''.join(random.choices('0123456789', k=20))
    boundary_longer: str = '--' + boundary
    total: str = ''
    for opt in options:
        total += boundary_longer + '\r\n'
        total += 'Content-Disposition: form-data; name="' + opt + '"\r\n\r\n'
        total += options[opt] + '\r\n'
    total += boundary_longer + '--\r\n'
    return total, boundary

def get_csrf_token(string: str) -> str:
    """Returns the first CSRF token appearing in the string."""
    if match := re.search('csrftoken = "(.*?)"', string):
        return match.group(0)
    raise RuntimeError ('failed to read csrf token')

def rename_timetable (timetable_id: int, new_name: str, cookies):
    """Changes timetable's name to new_name."""
    edit_request = requests.get(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/edytuj', 'plan_id': timetable_id},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    csrftoken: str = get_csrf_token(edit_request.text)
    payload, boundary = create_form_str({
        '_action': 'home/plany/zmienNazwe',
        'plan_id': str(timetable_id),
        'csrftoken': csrftoken,
        'nazwa': new_name
    })
    requests.post(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/zmienNazwe', 'plan_id': timetable_id},
        data=payload,
        headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def get_all_timetables_ids (cookies) -> list[int]:
    """Returns ids of all user's timetables."""
    list_timetables_request = requests.get (
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/index'},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    return re.findall(r'data-plan-id="(\d*)"', list_timetables_request.text)

def copy_timetable (timetable_id: int, cookies):
    """Creates a copy of a timetable."""
    requests.get(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/skopiuj', 'plan_id': timetable_id},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

def duplicate_timetable (timetable_id: int, num: int, name: str, cookies) -> list[int]:
    """Duplicates the timetable with given timetable_id num times, numbers the duplicates
    and returns their ids."""
    previous_timetables_ids: set[int] = set(get_all_timetables_ids(cookies))
    for _ in range (num):
        copy_timetable(timetable_id, cookies)
    # get all timetables (now including the copies)
    current_timetables_ids: list[int] = get_all_timetables_ids(cookies)
    # ids of the copies
    new_timetables_ids = [timetable_id for timetable_id in current_timetables_ids
                          if timetable_id not in previous_timetables_ids]
    # rename the copies
    for current_index, changed_timetable_id in enumerate(new_timetables_ids):
        rename_timetable(changed_timetable_id, name + ' ' + str(current_index), cookies)
        print ('duplicated timetable ', current_index)

    return new_timetables_ids

ODD_DAYS = 1
EVEN_DAYS = 2
ALL_DAYS = ODD_DAYS | EVEN_DAYS

def transform_time (hours_str: str, minutes_str: str):
    """Converts time into a decimal,
    adjusting for actual length of the class."""
    hours = int(hours_str)
    minutes = int(minutes_str)
    if minutes == 0 and hours != 10:
        hours -= 1
        minutes = 45
    return hours + minutes/60

def get_weekday_polish(string: str) -> str | None:
    """Returns first weekday (in Polish) appearing in the string."""
    if match := re.search(r'poniedziałek|wtorek|środa|czwartek|piątek', string):
        return match.group(0)
    return None

def get_parity_polish(string: str) -> str:
    """Returns first parity descriptor (in Polish) appearing in the string."""
    if match := re.search(r'nieparzyste|parzyste|każd', string):
        return match.group(0)
    raise RuntimeError ('failed to read parity')

def parity_to_int_polish(parity: str) -> int:
    """Converts parity (in Polish) into an int representaion."""
    match parity:
        case 'nieparzyste':
            return ODD_DAYS
        case 'parzyste':
            return EVEN_DAYS
        case 'każd':
            return ALL_DAYS
        case _:
            raise ValueError('parity is wrong')

def get_entry_data (entry: bs4.element.Tag):
    """Retrieves info about a single timetable entry."""
    name = entry.find_all('div')[0].string
    dates = ''
    i: bs4.element.Tag
    for i in entry.find_all('span'):
        if i.string is None:
            continue
        if re.search (r'\d*:\d*', i.string):
            dates = i.string

    name_match = typing.cast (re.Match[str], re.search (r'^([A-Z]*),\s*gr\.\s*(\d*)', name))
    time_match = typing.cast(re.Match[str], re.search(r'(\d*):(\d*) - (\d*):(\d*)', dates))

    data = {
        'classtype': name_match.group(1),
        'group_num': name_match.group(2),
        'day': get_weekday_polish(dates),
        'parity': parity_to_int_polish(get_parity_polish(dates)),
        'course': entry['name-id'],
        'time_from': transform_time (time_match.group(1), time_match.group(2)),
        'time_to': transform_time (time_match.group(3), time_match.group(4))
    }
    return data

@dataclass
class HourEntry:
    """Class representing a single class hour."""
    day: str
    parity: int
    time_from: int
    time_to: int

    def __str__ (self):
        return ('day: ' + self.day + ' parity: ' + str(self.parity)
                + ' from: ' + str(self.time_from) + ' to: ' + str(self.time_to))
    def __eq__(self, other):
        if not isinstance(other, HourEntry):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return (self.day == other.day and self.parity == other.parity
                and self.time_from == other.time_from)
    def __hash__(self):
        return hash((self.day, self.parity, self.time_from, self.time_to))

def do_hours_collide (l: HourEntry, r: HourEntry) -> bool:
    """Checks if two HourEntries overlap."""
    if l.day != r.day:
        return False
    if l.parity & r.parity == 0:
        return False
    return l.time_from <= r.time_to and l.time_to >= r.time_from

@dataclass
class GroupEntry:
    """Class representing a class group.
    If multiple groups have the same properties (course, classtype, hours),
    they might be grouped into a single GroupEntry with their numbers in group_nums."""

    group_nums: list[str] = field(default_factory=list)
    course: str = ""
    classtype: str = ""
    hours: set[HourEntry] = field(default_factory=set)

    def __str__ (self):
        return ('group: ' + str(self.group_nums) +
                ' from ' + self.course + ' ' + self.classtype + '\n' +
                '\n'.join(str(hour) for hour in self.hours))

def do_groups_collide (l: GroupEntry, r: GroupEntry) -> bool:
    """Checks if two GroupEntries overlap in time."""
    return any(do_hours_collide(hour_l, hour_r) for hour_l in l.hours for hour_r in r.hours)

def evaluate_timetable_time (timetable: list[GroupEntry], _: pathlib.Path) -> int:
    """Returns timetable badness with regard to the days' length, their start and end."""
    # mapping hours of all classes taking place at a given day to that day
    map_days_to_hours: dict[tuple[str, int], list[HourEntry]] = defaultdict(list[HourEntry])

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
def evaluate_timetable_custom (timetable: list[GroupEntry], path: pathlib.Path) -> int:
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

CLASSTYPES = {
    "Laboratorium": 'LAB',
    "Wykład": 'WYK',
    "Ćwiczenia": 'CW',
    "Wychowanie fizyczne": "WF"
}
def get_classtype_polish(string: str) -> str:
    """Returns first classtype (in Polish) appearing in the string."""
    pattern = r'(?:' + '|'.join(CLASSTYPES.keys()) + ')'
    if class_type_match := re.search(pattern, string):
        return CLASSTYPES[class_type_match.group(0)]
    return "Unknown classtype"

def split_course(timetable_id: int, n: int, groups: dict[str, GroupEntry], cookies):
    """Split n-th unsplit course entry in the timetable, keeping only given groups.
    Groups must be sorted by classtype into lists."""
    # groups: [classtype, GroupEntry]
    split_list_request = requests.get(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/rozbijWpis', 'plan_id': timetable_id, 'nr': n},
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

        classtype: str = get_classtype_polish(tr_span.contents[0].text)

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
        'csrftoken': get_csrf_token(split_list_request.text)
    }
    form_dict.update({'entry' + str(on_index): 'on' for on_index in remaining_indices})

    payload, boundary = create_form_str(form_dict)
    requests.post(
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/rozbijWpis', 'plan_id': timetable_id},
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
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/edytuj', 'plan_id': timetable_id},
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

def merge_groups_by_time(groups: list[GroupEntry]) -> list[GroupEntry]:
    """Returns list with groups merged by their hours (all group numbers are in group_nums)."""
    merged_groups: list[GroupEntry] = []
    for group in groups:
        for merged_group in merged_groups:
            if group.hours == merged_group.hours:
                merged_group.group_nums.extend(group.group_nums)
                break
        else:
            merged_groups.append(group)
    return merged_groups

def get_groups_from_timetable (timetable_id: int, cookies) -> list[list[GroupEntry]]:
    """Returns all groups appearing in the timetable,
    grouped in lists by their course units."""
    timetable_page = requests.get (
        USOSWEB_KONTROLER,
        params={'_action': 'home/plany/pokaz',
                'plan_id': timetable_id, 'plan_division': 'semester'},
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )

    print ('downloaded timetable')

    whole_timetable_soup = BeautifulSoup (timetable_page.content, 'html.parser')
    all_timetable_entries = whole_timetable_soup.find_all ('timetable-entry')
    all_timetable_entries_data = [get_entry_data(i) for i in all_timetable_entries]

    tt_entries_by_course_unit = defaultdict(list)
    for data in all_timetable_entries_data:
        tt_entries_by_course_unit[(data['course'], data['classtype'])].append(data)

    # all groups, grouped in lists by their course units
    all_groups: list[list[GroupEntry]] = []

    for course_unit, timetable_entries in tt_entries_by_course_unit.items():
        # [group number : GroupEntry] - groups belonging to the current course unit
        current_groups: dict [str, GroupEntry] = {}

        for timetable_entry in timetable_entries:
            group_num = timetable_entry['group_num']
            if group_num not in current_groups:
                current_groups[group_num] = GroupEntry(
                    group_nums = [group_num],
                    course = course_unit[0],
                    classtype = course_unit[1]
                )

            current_hour = HourEntry(
                day = timetable_entry['day'],
                parity = timetable_entry['parity'],
                time_from = timetable_entry['time_from'],
                time_to = timetable_entry['time_to']
            )
            current_groups[group_num].hours.add(current_hour)

        all_groups.append(merge_groups_by_time(list(current_groups.values())))

    return all_groups

def list_possible_timetables (all_course_units: list[list[GroupEntry]]):
    """Returns a list of all timetables with non-colliding groups."""
    current_timetables: list[list[GroupEntry]] = [[]]
    for course_unit in all_course_units:
        # course unit is a class type (like WYK/CW) associated with a course,
        # that consists of groups
        new_timetables: list[list[GroupEntry]] = []
        for curr_timetable in current_timetables:
            for new_group in course_unit:
                if not any(do_groups_collide(new_group, curr_group)
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
    groups: list[list[GroupEntry]] = field(default_factory=list)
    config_path: pathlib.Path = field(default_factory=pathlib.Path)

    template_timetable_id: int = -1

    def __str__ (self):
        return 'name: ' + self.name + ' evaluator: ' + self.evaluator

def read_dydactic_cycle() -> str:
    """Returns the dydactic cycle."""
    if words := read_words_from_file('./config/cycle'):
        return words[0]
    raise RuntimeError('Failed to read dydactic cycle')

def read_personal_config(path: pathlib.Path) -> (set[str], str):
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
    template_timetable_name = 'automatic_template_' + path.name + '_' + session_hash
    # create a timetable with all courses
    timetable_id: int = create_timetable(template_timetable_name, cookies)
    for course in courses:
        add_course_to_timetable(timetable_id, course, dydactic_cycle, cookies)

    return PlannerUnit(
        name = path.name,
        courses = courses,
        evaluator = evaluator,
        template_timetable_id= timetable_id,
        groups = get_groups_from_timetable(timetable_id, cookies),
        config_path = path
    )

def get_top_timetables(planner_unit: PlannerUnit, n: int) -> list[(list[GroupEntry], int)]:
    """Returns top n timetables with scores for a given planner unit."""
    possible_timetables = list_possible_timetables(planner_unit.groups)
    timetables_with_values = [
        (timetable, EVALUATORS[planner_unit.evaluator](timetable, planner_unit.config_path))
        for timetable in possible_timetables
    ]
    # sort timetables by badness, return top n
    return sorted(timetables_with_values, key=lambda x: x[1])[:n]

def main() -> int:
    """Calculates the best possible timetables according to config and creates them in USOS."""
    dydactic_cycle: str = read_dydactic_cycle()

    current_hash = ''.join(random.choices('ABCDEFGH', k=6))
    print ('starting run:', current_hash)
    username = input('username:')
    password = getpass()
    php_session_cookies = log_in_to_usos (username, password)

    all_planner_units: list[PlannerUnit] = []

    config_directory: pathlib.Path = pathlib.Path ('./config')
    personal_configs = [directory for directory
                        in config_directory.iterdir() if directory.is_dir()]

    for personal_config in personal_configs:
        current_unit = init_planner_unit_from_config(
            personal_config,
            current_hash,
            dydactic_cycle,
            php_session_cookies
        )
        print(current_unit)
        all_planner_units.append(current_unit)

    for current_unit in all_planner_units:
        top_timetables = get_top_timetables(current_unit, NUM_TIMETABLES)
        # ids of copies of the original timetable
        timetable_instance_ids: list[int] = (
            duplicate_timetable(
                current_unit.template_timetable_id,
                len(top_timetables),
                'automatic_instance_' + current_unit.name + '_' + current_hash + '__',
                php_session_cookies
            )
        )

        # recreate the top timetables in USOS
        for (timetable, _), timetable_id in zip(top_timetables, timetable_instance_ids):

            course_unit_to_groups: dict[tuple[str, str], GroupEntry] = {
                (group.course, group.classtype) : group for group in timetable
            }
            split_timetable (timetable_id, course_unit_to_groups, php_session_cookies)
            print ('shattered timetable')
    return 0

if __name__ == '__main__':
    sys.exit(main())
