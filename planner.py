import requests
import re
import typing
from bs4 import BeautifulSoup
import bs4
import random
from getpass import getpass

NUM_PLANS = 3

#   logs to usos and returns cookies with php session
def log_in_to_usos (username, password):

    r1 = requests.get('https://logowanie.uw.edu.pl/cas/login')

    cookies = r1.cookies

    lt = re.findall ('name="lt" value="(.*?)"', r1.text)[0]
    execution = re.findall ('name="execution" value="(.*?)"', r1.text)[0]
    event_id = re.findall ('name="_eventId" value="(.*?)"', r1.text)[0]

    r2 = requests.post('https://logowanie.uw.edu.pl/cas/login',
                       data= {'lt': lt, 'execution': execution, '_eventId': event_id, 'username': username, 'password': password, 'jsessionid': r1.cookies['JSESSIONID']}, cookies=r1.cookies)

    cookies.update(r2.cookies)

    r3 = requests.get ('https://logowanie.uw.edu.pl/cas/login', params={'service': 'https://usosweb.mimuw.edu.pl/kontroler.php?_action=news/default', 'gateway': 'true'}, cookies=cookies)

    return r3.cookies

#   creates plan with given subjects and returns its id
def create_plan (name: str, dydactic_cycle: str, subjects: list[str], cookies) -> int:
    create_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/utworz', 'nazwa': name}, cookies=cookies)

    plan_id = re.findall (r'plan_id=(\d*)', create_request.url)[0]
    for subject in subjects:
        requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/dodajWpis', 'plan_id': plan_id, 'klasa': 'P', 'prz_kod': subject, 'cdyd_kod': dydactic_cycle}, cookies=cookies)
    return plan_id

#   creates multiform post payload and returns it and the boundary
def create_form_str (options: dict[str, str]) -> tuple[str, str]:
    boundary: str = '-' * 27 +  ''.join(random.choice('0123456789') for _ in range(20))
    boundary_longer: str = '--' + boundary
    total: str = ''
    for opt in options:
        total += boundary_longer + '\r\n'
        total += 'Content-Disposition: form-data; name="' + opt + '"\r\n\r\n'
        total += options[opt] + '\r\n';
    total += boundary_longer + '--\r\n'
    return (total, boundary)

#   takes a plan id, duplicates it num times and returns ids of new plans
def duplicate_plan (plan: int, num: int, name: str, cookies) -> list[int]:
    list_plans_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/index'}, cookies=cookies)
    previous_plan_ids: set[str] = set(re.findall(r'data-plan-id="(\d*)"', list_plans_request.text))
    for _ in range (num):
        requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/skopiuj', 'plan_id': plan}, cookies=cookies)
    list_plans_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/index'}, cookies=cookies)
    current_plan_ids: list[int] = re.findall(r'data-plan-id="(\d*)"', list_plans_request.text)
    #new_plan_ids: set[int] = current_plan_ids.difference (previous_plan_ids)
    new_plan_ids: list[int] = []
    for plan_id in current_plan_ids:
        if plan_id not in previous_plan_ids:
            new_plan_ids.append (plan_id)

    for current_index, changed_plan_id in enumerate(new_plan_ids):
        change_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/edytuj', 'plan_id': changed_plan_id}, cookies=cookies)
        csrftoken: str = typing.cast(re.Match, re.search ('csrftoken = "(.*?)"', change_request.text))[1]
        new_name = name + ' ' + str(current_index)
        payload, boundary = create_form_str ({'_action': 'home/plany/zmienNazwe', 'plan_id': str(changed_plan_id), 'csrftoken': csrftoken, 'nazwa': new_name})
        requests.post ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/zmienNazwe', 'plan_id': changed_plan_id}, data=payload, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary}, cookies=cookies)
        print ('duplicated plan ', current_index)

    return new_plan_ids

current_hash = ''.join(random.choice('ABCDEFGH') for _ in range(6))
print ('starting run:', current_hash)

dydactic_cycle = '2024Z'
dydactic_cycle = '2024Z'
with open ('codes', 'r') as f:
    codes_file = f.read()
    subjects = re.findall(r'\S+', codes_file)

username = input('username:')
password = getpass()

php_session_cookies = log_in_to_usos (username, password)

print ('logged in to usos')

new_plan_name = 'automatic_template_' + current_hash
plan_id: int = create_plan (new_plan_name, dydactic_cycle, subjects, php_session_cookies)

print ('created plan')

plan_instence_ids: list[int] = duplicate_plan (plan_id, NUM_PLANS, 'automatic_instance_' + current_hash + '__', php_session_cookies)

ODD_DAYS = 1
EVEN_DAYS = 2
ALL_DAYS = ODD_DAYS | EVEN_DAYS

plan_page = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/pokaz', 'plan_id': plan_id, 'plan_division': 'semester'}, cookies=php_session_cookies)

print ('downloaded plan')
whole_plan_soup = BeautifulSoup (plan_page.content, 'html.parser')

def transform_time (hours: str, minutes: str):
    hours_i = int(hours)
    minutes_i = int(minutes)
    if (minutes_i == 0 and hours_i != 10):
        hours_i -= 1
        minutes_i = 45
    return (hours_i + minutes_i/60)

def get_entry_data (entry: bs4.element.Tag):
    name = entry.find_all('div')[0].string
    dates = ''
    i: bs4.element.Tag
    for i in entry.find_all('span'):
        if i.string is None:
            continue
        if (re.search (r'\d*:\d*', i.string)):
            dates = i.string
    name_match = typing.cast (re.Match[str], re.search (r'^([A-Z]*),\s*gr\.\s*(\d*)', name))
    day_of_the_week = typing.cast (re.Match[str], re.search (r'((?:poniedziałek|wtorek|środa|czwartek|piątek))', dates))
    parity_str = typing.cast(re.Match[str], re.search(r'((?:nieparzyste|parzyste|każd))', dates))
    match (parity_str.group(1)):
        case 'nieparzyste':
            parity = ODD_DAYS
        case 'parzyste':
            parity = EVEN_DAYS
        case 'każd':
            parity = ALL_DAYS
        case _:
            raise ValueError('parity is wrong')

    time_match = typing.cast(re.Match[str], re.search(r'(\d*):(\d*) - (\d*):(\d*)', dates))

    data = {'type': name_match.group(1), 'group': name_match.group(2), 'day': day_of_the_week.group(1), 'parity': parity, 'subject': entry['name-id'], 'time_from': transform_time (time_match.group(1), time_match.group(2)), 'time_to': transform_time (time_match.group(3), time_match.group(4))}
    return data

entries = whole_plan_soup.find_all ('timetable-entry')

all_data = [get_entry_data(i) for i in entries]

all_groups = list(set([(data['subject'], data['type']) for data in all_data]))

group_to_options = {group: [] for group in all_groups}
for data in all_data:
    group_to_options[(data['subject'], data['type'])].append(data)


class hour_entry:
    day: str
    parity: int
    time_from: int
    time_to: int
    def __str__ (self):
        return 'day: ' + self.day + ' parity: ' + str(self.parity) + ' from: ' + str(self.time_from) + ' to: ' + str(self.time_to)
    def __eq__(self, other): 
        if not isinstance(other, hour_entry):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.day == other.day and self.parity == other.parity and self.time_from == other.time_from
    def __hash__(self):
        return hash((self.day, self.parity, self.time_from, self.time_to))

def do_hours_collide (l: hour_entry, r: hour_entry) -> bool:
    if (l.day != r.day):
        return False
    if (l.parity & r.parity == 0):
        return False
    return l.time_from <= r.time_to and l.time_to >= r.time_from

class group_entry:

    def __init__ (self):
        self.groups: list[str] = []
        self.subject: str = ""
        self.entry_type: str = ""
        self.hours: set[hour_entry] = set ()

    def __str__ (self):
        res =  'group: ' + str(self.groups) + ' from ' + self.subject + ' ' + self.entry_type
        for hour in self.hours:
            res += '\n' + str(hour)
        return res

def do_groups_collide (l: group_entry, r: group_entry) -> bool:
    for hour_l in l.hours:
        for hour_r in r.hours:
            if (do_hours_collide (hour_l, hour_r)):
                return True
    return False

all_total_entries: list[list[group_entry]] = []

for i in group_to_options:

    current_entry: list[group_entry] = []
    #current_entry.subject = i[0]
    #current_entry.entry_type = i[1]

    current_groups: dict [str, group_entry] = {}
    x: dict[str, typing.Any]
    for x in group_to_options[i]:
        if x['group'] not in current_groups:
            current_groups[x['group']] = group_entry()
            current_groups[x['group']].groups = [x['group']]
            current_groups[x['group']].subject = i[0]
            current_groups[x['group']].entry_type = i[1]
        current_hour = hour_entry()
        current_hour.day = x['day']
        current_hour.parity = x['parity']
        current_hour.time_from = x['time_from']
        current_hour.time_to = x['time_to']

        current_groups[x['group']].hours.add (current_hour)

    for group in current_groups.values():
        was_already: bool = False
        if (len(current_entry) > 0):
            for previous_group in current_entry:
                if (group.hours == previous_group.hours):
                    was_already = True
                    previous_group.groups.extend(group.groups)

        if (not was_already):
            current_entry.append (group)

    all_total_entries.append (current_entry)

current_plans: list[list[group_entry]]  = [[]]
for entry in all_total_entries:
    # entry is a subject (list of group entries)
    new_plans: list[list[group_entry]]  = []
    for old_plan in current_plans:
        for new_group in entry:
            can_be_added: bool = True
            for old_group in old_plan:
                if (do_groups_collide (old_group, new_group)):
                    can_be_added = False
                    break
            if (can_be_added):
                new_plans.append (old_plan.copy())
                new_plans[-1].append (new_group)
    current_plans = new_plans

def evaluate_plan (plan: list[group_entry]) -> int:
    map_days_to_hours: dict[tuple[str, int], list[hour_entry]] = {}
    for entry in plan:
        for hour in entry.hours:
            if (hour.parity == ALL_DAYS):
                if ((hour.day, EVEN_DAYS) not in map_days_to_hours):
                    map_days_to_hours[(hour.day, EVEN_DAYS)] = []
                if ((hour.day, ODD_DAYS) not in map_days_to_hours):
                    map_days_to_hours[(hour.day, ODD_DAYS)] = []

                map_days_to_hours[(hour.day, EVEN_DAYS)].append (hour)
                map_days_to_hours[(hour.day, ODD_DAYS)].append (hour)
            else:
                if ((hour.day, hour.parity) not in map_days_to_hours):
                    map_days_to_hours[(hour.day, hour.parity)] = []
                map_days_to_hours[(hour.day, hour.parity)].append (hour)

    day_lens: list[tuple[int,int]] = []
    for day in map_days_to_hours:
        current_hour_list = map_days_to_hours[day]
        to = max ([hour.time_to for hour in current_hour_list])
        fro = min ([hour.time_from for hour in current_hour_list])
        day_lens.append ((fro, to))
    
    res = 0
    for l in day_lens:
        res += 20
        res += l[1]-l[0]
        if (l[0] < 10):
            res += 2
        if (l[1] > 15):
            res += 2
        if (l[1] > 17):
            res += 10
        if (l[1] - l[0] > 9):
            res += 30
    return res

plans_with_values = [(plan, evaluate_plan(plan)) for plan in current_plans]

plans_with_values.sort (key=(lambda x: x[1]))

#   takes a dictionary from subject code to list of its groups
def shatter_plan (plan_id: int, groups: dict[tuple[str, str], group_entry], cookies):

    edit_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/edytuj', 'plan_id': plan_id}, cookies=cookies)
    edit_soup = BeautifulSoup (edit_request.content, 'html.parser')
    shattered_subjects: list[str] = []
    for tr in edit_soup.find_all ('tr'):
        span = tr.find('span')
        if span is not None:
            shattered_subjects.extend (span.contents)

    for subject in shattered_subjects:

        shatter_list_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/rozbijWpis', 'plan_id': plan_id, 'nr': 0}, cookies=cookies)

        csrftoken: str = typing.cast(re.Match, re.search ('csrftoken = "(.*?)"', shatter_list_request.text))[1]

        shatter_list_soup = BeautifulSoup (shatter_list_request.content, 'html.parser')

        left_indices: list[int] = []

        for current_index, tr in enumerate(shatter_list_soup.find_all ('tr')):
            tr_spans: list[bs4.Tag] = tr.find_all ('span')
            if (len(tr_spans) < 2):
                continue
            tr_span: bs4.Tag = tr_spans[-1]
            lesson_type: str = ""
            if (re.search ('Lab', tr_span.contents[0].text)):
                lesson_type = 'LAB'
            elif (re.search ('Wyk', tr_span.contents[0].text)):
                lesson_type = 'WYK'
            else:
                lesson_type = 'CW'

            group_num: str = typing.cast (re.Match, re.search (r'grupa nr (\d*)', tr_span.contents[1].text)).group(1)

            group_xd = groups[(subject, lesson_type)]
            if group_num in group_xd.groups:
                left_indices.append (current_index-1)

        form_dict: dict[str, str] = {'_action': 'home/plany/rozbijWpis', 'plan_id': str(plan_id), 'nr': '0', 'zapisz': '1',  'csrftoken': csrftoken, }
        for on_index in left_indices:
            form_dict['entry' + str(on_index)] = 'on'

        payload, boundary = create_form_str (form_dict)
        requests.post ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/rozbijWpis', 'plan_id': plan_id}, data=payload, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary}, cookies=cookies)


for i in range (min(NUM_PLANS, len(plans_with_values))):

    plan: list[group_entry] = plans_with_values[i][0]

    map_subjects_to_groups: dict[tuple[str, str], group_entry] = {}
    for group in plan:
        map_subjects_to_groups[(group.subject, group.entry_type)] = group

    shatter_plan (plan_instence_ids[i], map_subjects_to_groups, php_session_cookies)

    print ('shattered plan')
