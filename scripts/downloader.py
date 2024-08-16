"""Downloads course data from USOSweb (to later use in judger) and saves it in a JSON file."""
import json
from collections import defaultdict
import usos_tools.login
import usos_tools.timetables as tt
from scripts.utils import get_login_credentials, get_cycle, read_words_from_file

def main(args):
    credentials = get_login_credentials (args)
    cycle = get_cycle (args)

    php_session_cookies = usos_tools.login.log_in_to_usos (*credentials)

    codes = read_words_from_file ('codes')

    with tt.TmpTimetable(php_session_cookies) as timetable:
        for code in codes:
            tt.add_course_to_timetable(
                timetable.timetable_id,
                code,
                cycle,
                php_session_cookies
            )
        group_data = tt.get_groups_from_timetable(
            timetable.timetable_id, False, php_session_cookies
            )

        entries = defaultdict (lambda: defaultdict (lambda: defaultdict (list)))

        for course_name, group_data_of_name in group_data.items():
            for entry_type, groups in group_data_of_name.items():
                for group in groups:
                    for hour in group.hours:
                         relevant_data = {
                             'day': hour.day,
                             'parity': hour.parity,
                             'lesson': int(hour.time_from-8)//2,
                             'teacher': group.teacher
                         }
                         if len(group.group_nums) != 1:
                             raise RuntimeError('Group has wrong number of nums')
                         # gets any group num
                         group_num = next(iter(group.group_nums))
                         entries[course_name][entry_type][group_num].append (relevant_data)


    json_str = json.dumps(entries, indent=2)

    with open("site/data.js", 'w', encoding='utf-8') as f:
        f.write ('let data=')
        f.write (json_str)
