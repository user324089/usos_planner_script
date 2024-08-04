import requests
import re
import typing
from bs4 import BeautifulSoup
import bs4
import random
from getpass import getpass
import json
import sys

ODD_DAYS = 1
EVEN_DAYS = 2
ALL_DAYS = ODD_DAYS | EVEN_DAYS

def read_words_from_file (filename: str) -> list[str]:
    try:
        with open (filename, 'r') as f:
            whole_str: str = f.read()
            words: list[str] = re.findall(r'\S+', whole_str)
            return words
    except FileNotFoundError:
        return []

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
    print ('logged in to usos')

    return r3.cookies

#   creates plan with given subjects and returns its id
def create_plan (name: str, dydactic_cycle: str, subjects: list[str], cookies) -> int:
    create_request = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/utworz', 'nazwa': name}, cookies=cookies)

    plan_id = re.findall (r'plan_id=(\d*)', create_request.url)[0]
    for subject in subjects:
        requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/dodajWpis', 'plan_id': plan_id, 'klasa': 'P', 'prz_kod': subject, 'cdyd_kod': dydactic_cycle}, cookies=cookies)
    print ('created plan:', name)
    return plan_id

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

    #print (name_match[0], entry['name-id'])
    person_div = entry.find ('div', {'slot': 'dialog-person'})
    teacher: str = 'UNKNOWN'
    if person_div is not None:
        teacher = person_div.text.strip().replace (',', '')

    data = {'type': name_match.group(1), 'group': name_match.group(2), 'day': day_of_the_week.group(1), 'parity': parity, 'subject': entry['name-id'], 'time_from': transform_time (time_match.group(1), time_match.group(2)), 'time_to': transform_time (time_match.group(3), time_match.group(4)), 'teacher': teacher}
    return data

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

class group_entry:

    def __init__ (self):
        self.groups: list[str] = []
        self.subject: str = ""
        self.entry_type: str = ""
        self.hours: set[hour_entry] = set ()
        self.teacher: str = ''

    def __str__ (self):
        res =  'group: ' + str(self.groups) + ' from ' + self.subject + ' ' + self.entry_type
        for hour in self.hours:
            res += '\n' + str(hour)
        return res

def get_groups_from_plan (plan: int, cookies) -> list[list[group_entry]]:
    plan_page = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/pokaz', 'plan_id': plan, 'plan_division': 'semester'}, cookies=cookies)

    print ('downloaded plan')
    whole_plan_soup = BeautifulSoup (plan_page.content, 'html.parser')

    entries = whole_plan_soup.find_all ('timetable-entry')

    all_data = [get_entry_data(i) for i in entries]

    all_groups = list(set([(data['subject'], data['type']) for data in all_data]))

    group_to_options = {group: [] for group in all_groups}
    for data in all_data:
        group_to_options[(data['subject'], data['type'])].append(data)


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
                current_groups[x['group']].teacher = x['teacher']
            current_hour = hour_entry()
            current_hour.day = x['day']
            current_hour.parity = x['parity']
            current_hour.time_from = x['time_from']
            current_hour.time_to = x['time_to']

            current_groups[x['group']].hours.add (current_hour)

        all_total_entries.append ([group for group in current_groups.values()])

    return all_total_entries


#-------------------------------------

words_in_cycle_file: list[str] = read_words_from_file ('cycle')
if (len(words_in_cycle_file) != 1):
    print ('failed to read dydactic cycle')
    sys.exit (1)
dydactic_cycle: str = words_in_cycle_file[0]

current_hash = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(20))
username = input('username:')
password = getpass()
php_session_cookies = log_in_to_usos (username, password)

subjects: list[str] = read_words_from_file ('codes')
plan_id: int = create_plan (current_hash, dydactic_cycle, subjects, php_session_cookies)
groups = get_groups_from_plan (plan_id, php_session_cookies)


requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/usun', 'plan_id': plan_id}, cookies=php_session_cookies)

entries = {}

for lesson in groups:
    for group in lesson:

        if group.subject not in entries:
            entries[group.subject] = {}
        if group.entry_type not in entries[group.subject]:
            entries[group.subject][group.entry_type] = {}

        group_name = group.groups[0]
        entries[group.subject][group.entry_type][group_name] = []
        for hour in group.hours:
            parity: str = 'all'
            if (hour.parity == ODD_DAYS):
                parity = 'odd'
            elif (hour.parity == EVEN_DAYS):
                parity = 'even'

            relevant_data = {'day': hour.day, 'parity': parity, 'lesson': int(hour.time_from-8)//2, 'teacher': group.teacher}
            entries[group.subject][group.entry_type][group_name].append (relevant_data)


json_str = json.dumps(entries, indent=2)

with open("site/data.js", 'w') as f:
    f.write ('let data=')
    f.write (json_str)
