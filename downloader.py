import argparse
from getpass import getpass
import json
import sys
import usos_tools.login
import usos_tools.timetables as tt
from collections import defaultdict
import sys

def read_words_from_file (filename: str) -> list[str]:
    """Returns a list of all words in the file."""
    try:
        with open (filename, 'r', encoding="utf-8") as f:
            return f.read().split()
    except FileNotFoundError:
        return []

class programArgumentParser:
    def __init__ (self):
        self.parser = argparse.ArgumentParser(description='Usos planner')
        self.parser.add_argument('-l', '--login', metavar='FILE', help='Usos login data file')
        self.parser.add_argument('-c', '--cycle', help='Cycle of subjects')
        self.args = self.parser.parse_args()

        self.login_credentials: tuple[str, str] | None = None
        self.cycle: str | None = None

    def get_login_credentials(self) -> tuple[str, str]:
        """Gets login credentials from a file or from the user."""
        if self.login_credentials:
            return self.login_credentials

        if self.args.login:
            login_filename: str = self.args.login
            with open (login_filename, 'r', encoding="utf-8") as login_file:
                credentials: list[str] = login_file.read().split('\n')
                if len(credentials) < 2:
                    raise RuntimeError('Failed to read credentials')
                username = credentials[0]
                password = credentials[1]
        else:
            username = input('username:')
            password = getpass()
        return username, password

    def get_cycle (self) -> str:
        if self.cycle is not None:
            return self.cycle
        if self.args.cycle:
            self.cycle = self.args.cycle
        else:
            self.cycle = input('cycle:')
        return self.cycle


def main () -> int:

    program_arg_parser = programArgumentParser ()
    credentials = program_arg_parser.get_login_credentials()

    cycle = program_arg_parser.get_cycle()

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
                         relevant_data = {'day': hour.day, 'parity': hour.parity, 'lesson': int(hour.time_from-8)//2, 'teacher': group.teacher}
                         if (len(group.group_nums) != 1):
                             print ('error, group has wrong number of names')
                             return 1
                         # gets any group num
                         group_num = next(iter(group.group_nums))
                         entries[course_name][entry_type][group_num].append (relevant_data)


    json_str = json.dumps(entries, indent=2)

    with open("site/data.js", 'w') as f:
        f.write ('let data=')
        f.write (json_str)

    return 0

if __name__ == '__main__':
    sys.exit(main())
