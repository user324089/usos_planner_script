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
import requests
from bs4 import BeautifulSoup
import bs4

NUM_PLANS = 3

def read_words_from_file (filename: str) -> list[str]:
    """Returns a list of all words in the file."""
    try:
        with open (filename, 'r') as f:
            return f.read().split()
    except FileNotFoundError:
        return []

def log_in_to_usos (username, password):
    """Logs into USOS and returns cookies with PHP session."""

    r1 = requests.get('https://logowanie.uw.edu.pl/cas/login', timeout=20)
    cookies = r1.cookies

    lt = re.findall ('name="lt" value="(.*?)"', r1.text)[0]
    execution = re.findall ('name="execution" value="(.*?)"', r1.text)[0]
    event_id = re.findall ('name="_eventId" value="(.*?)"', r1.text)[0]

    r2 = requests.post('https://logowanie.uw.edu.pl/cas/login',
                       data= {'lt': lt, 'execution': execution, '_eventId': event_id,
                              'username': username, 'password': password,
                              'jsessionid': r1.cookies['JSESSIONID']},
                       cookies=r1.cookies, timeout=20)
    cookies.update(r2.cookies)

    r3 = requests.get ('https://logowanie.uw.edu.pl/cas/login',
                       params={'service': 'https://usosweb.mimuw.edu.pl/kontroler.php?_action=news/default',
                               'gateway': 'true'},
                       cookies=cookies, timeout=20)
    print ('logged in to usos')
    return r3.cookies

def add_course_to_plan(plan_id: int, course_code: str, dydactic_cycle: str, cookies):
    """Adds the course (all groups) to the plan."""
    requests.get('https://usosweb.mimuw.edu.pl/kontroler.php',
                 params={'_action': 'home/plany/dodajWpis', 'plan_id': plan_id,
                         'klasa': 'P', 'prz_kod': course_code, 'cdyd_kod': dydactic_cycle},
                 cookies=cookies, timeout=20)

def create_plan (name: str, cookies) -> int:
    """Creates an empty plan in USOS and returns its id."""
    create_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php',
                                   params={'_action': 'home/plany/utworz', 'nazwa': name},
                                   cookies=cookies, timeout=20)
    print ('created plan:', name)
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

def get_csrf_token(string: str) -> str | None:
    """Returns the first CSRF token appearing in the string."""
    if match := re.search('csrftoken = "(.*?)"', string):
        return match.group(0)
    return None

def rename_plan (plan_id: int, new_name: str, cookies):
    """Changes plan name to new_name."""
    edit_request = requests.get('https://usosweb.mimuw.edu.pl/kontroler.php',
                                  params={'_action': 'home/plany/edytuj',
                                          'plan_id': plan_id},
                                  cookies=cookies, timeout=20)

    csrftoken: str = get_csrf_token(edit_request.text)
    payload, boundary = create_form_str({'_action': 'home/plany/zmienNazwe',
                                         'plan_id': str(plan_id),
                                         'csrftoken': csrftoken,
                                         'nazwa': new_name})
    requests.post('https://usosweb.mimuw.edu.pl/kontroler.php',
                  params={'_action': 'home/plany/zmienNazwe', 'plan_id': plan_id},
                  data=payload,
                  headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
                  cookies=cookies, timeout=20)

def get_all_plan_ids (cookies) -> list[int]:
    """Returns ids of all user plans."""
    list_plans_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php',
                                       params={'_action': 'home/plany/index'},
                                       cookies=cookies, timeout=20)
    return re.findall(r'data-plan-id="(\d*)"', list_plans_request.text)

def copy_plan (plan_id: int, cookies):
    """Creates a copy of a plan."""
    requests.get('https://usosweb.mimuw.edu.pl/kontroler.php',
                 params={'_action': 'home/plany/skopiuj', 'plan_id': plan_id},
                 cookies=cookies, timeout=20)

def duplicate_plan (plan_id: int, num: int, name: str, cookies) -> list[int]:
    """Duplicates the plan with given plan_id num times, numbers the duplicates
    and returns their ids."""
    previous_plan_ids: set[int] = set(get_all_plan_ids(cookies))
    for _ in range (num):
        copy_plan(plan_id, cookies)
    # get all plans (now including the copies)
    current_plan_ids: list[int] = get_all_plan_ids(cookies)
    # ids of the copies
    new_plan_ids = [plan_id for plan_id in current_plan_ids if plan_id not in previous_plan_ids]
    # rename the copies
    for current_index, changed_plan_id in enumerate(new_plan_ids):
        rename_plan(changed_plan_id, name + ' ' + str(current_index), cookies)
        print ('duplicated plan ', current_index)

    return new_plan_ids

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
    if match := re.search(r'(?:poniedziałek|wtorek|środa|czwartek|piątek)', string):
        return match.group(0)
    return None

def get_parity_polish(string: str) -> str | None:
    """Returns first parity descriptor (in Polish) appearing in the string."""
    if match := re.search(r'(?:nieparzyste|parzyste|każd)', string):
        return match.group(0)
    return None

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
    """Retrieves group info."""
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

    data = {'type': name_match.group(1),
            'group': name_match.group(2),
            'day': get_weekday_polish(dates),
            'parity': parity_to_int_polish(get_parity_polish(dates)),
            'subject': entry['name-id'],
            'time_from': transform_time (time_match.group(1), time_match.group(2)),
            'time_to': transform_time (time_match.group(3), time_match.group(4))}
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
    If multiple groups have the same properties (subject, entry type, hours),
    they might be grouped into a single GroupEntry with their numbers in group_nums."""

    group_nums: list[str] = field(default_factory=list)
    subject: str = ""
    entry_type: str = ""
    hours: set[HourEntry] = field(default_factory=set)

    def __str__ (self):
        return ('group: ' + str(self.group_nums) +
                ' from ' + self.subject + ' ' + self.entry_type + '\n' +
                '\n'.join(str(hour) for hour in self.hours))

def do_groups_collide (l: GroupEntry, r: GroupEntry) -> bool:
    """Checks if two GroupEntries overlap in time."""
    return any(do_hours_collide(hour_l, hour_r) for hour_l in l.hours for hour_r in r.hours)

def evaluate_plan_time (plan: list[GroupEntry]) -> int:
    """Returns plan badness with regard to the days' length, their start and end."""
    # mapping hours of all classes taking place at a given day to that day
    map_days_to_hours: dict[tuple[str, int], list[HourEntry]] = defaultdict(list[HourEntry])

    for entry in plan:
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

evaluators = {'time': evaluate_plan_time}

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

#   takes a dictionary from subject code to list of its groups
def shatter_plan (plan_id: int, groups: dict[tuple[str, str], GroupEntry], cookies):
    """Create a schedule containing given groups
    by splitting a preexisting schedule given by plan_id."""
    # groups: [[course, classtype], groups]

    edit_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php',
                                 params={'_action': 'home/plany/edytuj', 'plan_id': plan_id},
                                 cookies=cookies, timeout=20)
    edit_soup = BeautifulSoup (edit_request.content, 'html.parser')

    # course units appearing in the plan
    shattered_courses: list[str] = []
    for tr in edit_soup.find_all ('tr'):
        if span := tr.find('span'):
            shattered_courses.extend(span.contents)

    # iterating through all the courses in the plan
    for course in shattered_courses:

        shatter_list_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php',
                                             params={'_action': 'home/plany/rozbijWpis',
                                                     'plan_id': plan_id, 'nr': 0},
                                             cookies=cookies, timeout=20)

        csrftoken: str = get_csrf_token(shatter_list_request.text)

        shatter_list_soup = BeautifulSoup (shatter_list_request.content, 'html.parser')
        # remaining groups
        remaining_indices: list[int] = []

        for current_index, tr in enumerate(shatter_list_soup.find_all ('tr')):
            tr_spans: list[bs4.Tag] = tr.find_all ('span')
            if len(tr_spans) < 2:
                continue
            tr_span: bs4.Tag = tr_spans[-1]

            classtype: str = get_classtype_polish(tr_span.contents[0].text)

            if (group_num_match := re.search(r'grupa nr (\d*)', tr_span.contents[1].text)) is None:
                raise TypeError("Group number not found.")
            group_num = group_num_match.group(1)

            if group_num in groups[(course, classtype)].group_nums:
                remaining_indices.append (current_index-1)

        form_dict: dict[str, str] = {'_action': 'home/plany/rozbijWpis',
                                     'plan_id': str(plan_id),
                                     'nr': '0',
                                     'zapisz': '1',
                                     'csrftoken': csrftoken, }
        form_dict.update({'entry' + str(on_index) : 'on' for on_index in remaining_indices})

        payload, boundary = create_form_str (form_dict)
        requests.post ('https://usosweb.mimuw.edu.pl/kontroler.php',
                       params={'_action': 'home/plany/rozbijWpis', 'plan_id': plan_id},
                       data=payload,
                       headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
                       cookies=cookies, timeout=20)

#   takes plan id and returns and returns a list which contains a list of groups for every subject
def get_groups_from_plan (plan_id: int, cookies) -> list[list[GroupEntry]]:
    plan_page = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php',
                              params={'_action': 'home/plany/pokaz',
                                      'plan_id': plan_id,
                                      'plan_division': 'semester'},
                              cookies=cookies, timeout=20)

    print ('downloaded plan')
    whole_plan_soup = BeautifulSoup (plan_page.content, 'html.parser')

    entries = whole_plan_soup.find_all ('timetable-entry')

    all_data = [get_entry_data(i) for i in entries]

    all_groups = list({(data['subject'], data['type']) for data in all_data})

    group_to_options = {group: [] for group in all_groups}
    for data in all_data:
        group_to_options[(data['subject'], data['type'])].append(data)


    all_total_entries: list[list[GroupEntry]] = []

    for i in group_to_options:

        current_entry: list[GroupEntry] = []
        #current_entry.subject = i[0]
        #current_entry.entry_type = i[1]

        current_groups: dict [str, GroupEntry] = {}
        x: dict[str, typing.Any]
        for x in group_to_options[i]:
            if x['group'] not in current_groups:
                current_groups[x['group']] = GroupEntry(group_nums = [x['group']],
                                                        subject = i[0],
                                                        entry_type = i[1])

            current_hour = HourEntry(day = x['day'],
                                     parity = x['parity'],
                                     time_from = x['time_from'],
                                     time_to = x['time_to'])
            current_groups[x['group']].hours.add (current_hour)

        for group in current_groups.values():
            was_already: bool = False
            if len(current_entry) > 0:
                for previous_group in current_entry:
                    if group.hours == previous_group.hours:
                        was_already = True
                        previous_group.group_nums.extend(group.group_nums)

            if not was_already:
                current_entry.append (group)

        all_total_entries.append (current_entry)
    return all_total_entries

def list_possible_plans (all_course_units: list[list[GroupEntry]]):
    """Returns a list of all plans with non-colliding groups."""
    current_plans: list[list[GroupEntry]] = [[]]
    for course_unit in all_course_units:
        # course unit is a class type (like WYK/CW) associated with a course,
        # that consists of groups
        new_plans: list[list[GroupEntry]] = []
        for curr_plan in current_plans:
            for new_group in course_unit:
                if not any(do_groups_collide(new_group, curr_group) for curr_group in curr_plan):
                    new_plans.append(curr_plan.copy() + [new_group])
        current_plans = new_plans
    return current_plans

@dataclass
class PlannerUnit:
    """Class representing a timetable optimizer."""
    name: str = 'unnamed'
    evaluator: str = 'time'
    # all attended lessons
    lessons: set[str] = field(default_factory=set)
    # all groups of attended lessons
    groups: list[list[GroupEntry]] = field(default_factory=list)
    template_plan_id: int = -1

    def __str__ (self):
        return 'name: ' + self.name + ' evaluator: ' + self.evaluator

def main():
    # read dydactic cycle from file
    words_in_cycle_file: list[str] = read_words_from_file ('./config/cycle')
    if len(words_in_cycle_file) != 1:
        print ('failed to read dydactic cycle')
        sys.exit (1)
    dydactic_cycle: str = words_in_cycle_file[0]

    current_hash = ''.join(random.choices('ABCDEFGH', k=6))
    print ('starting run:', current_hash)
    username = input('username:')
    password = getpass()
    php_session_cookies = log_in_to_usos (username, password)

    all_planner_units: list[PlannerUnit] = []

    directory: pathlib.Path = pathlib.Path ('./config')
    for directory in directory.iterdir():
        if not directory.is_dir():
            continue
        current_unit: PlannerUnit = PlannerUnit (name = directory.name)

        # get all courses from codes file
        subjects: list[str] = read_words_from_file (str((directory / 'codes').resolve()))
        current_unit.lessons = set(subjects)

        # get chosen evaluation function
        evaluator_list: list[str] = read_words_from_file (str((directory / 'eval').resolve()))

        if len(evaluator_list) == 1 and evaluator_list[0] in evaluators:
            current_unit.evaluator = evaluator_list[0]

        template_plan_name = 'automatic_template_' + current_unit.name + '_' + current_hash

        # create plan with all courses
        plan_id: int = create_plan(template_plan_name, php_session_cookies)
        for subject in subjects:
            add_course_to_plan(plan_id, subject, dydactic_cycle, php_session_cookies)

        current_unit.template_plan_id = plan_id
        # get group info from the created plan
        current_unit.groups = get_groups_from_plan (plan_id, php_session_cookies)

        print (current_unit)
        all_planner_units.append (current_unit)

    for current_unit in all_planner_units:
        # ids of copies of the original plan
        plan_instance_ids: list[int] = (
            duplicate_plan (current_unit.template_plan_id, NUM_PLANS,
                            'automatic_instance_' + current_unit.name + '_' + current_hash + '__',
                            php_session_cookies))

        possible_plans = list_possible_plans (current_unit.groups)
        plans_with_values = [(plan, evaluators[current_unit.evaluator](plan))
                             for plan in possible_plans]
        # sort plans by badness
        plans_with_values.sort (key=lambda x: x[1])

        # recreate the top NUM_PLANS plans in USOS
        for i in range (min(NUM_PLANS, len(plans_with_values))):

            plan: list[GroupEntry] = plans_with_values[i][0]

            map_subjects_to_groups: dict[tuple[str, str], GroupEntry] = {
                (group.subject, group.entry_type) : group for group in plan
            }

            shatter_plan (plan_instance_ids[i], map_subjects_to_groups, php_session_cookies)

            print ('shattered plan')

if __name__ == '__main__':
    main()
