import re
from getpass import getpass
import usos_tools


def main ():
    username: str = input('username:')
    password: str = getpass()
    print ('enter regular expression:')
    expression: str = input()

    cookies = usos_tools.log_in_to_usos (username, password)
    for timetable_name, timetable_id in usos_tools.get_all_timetables (cookies):
        if re.match (expression, timetable_name):
            usos_tools.delete_timetable (timetable_id, cookies)

if __name__ == '__main__':
    main()
