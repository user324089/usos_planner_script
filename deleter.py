import re
from getpass import getpass
import usos_tools.login
import usos_tools.timetables as tt

def main ():
    username: str = input('username:')
    password: str = getpass()
    print ('enter regular expression:')
    expression: str = input()

    cookies = usos_tools.login.log_in_to_usos (username, password)
    for timetable_name, timetable_id in tt.get_all_timetables (cookies):
        if re.match (expression, timetable_name):
            tt.delete_timetable (timetable_id, cookies)

if __name__ == '__main__':
    main()
