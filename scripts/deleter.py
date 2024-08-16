"""Module for deleting selected timetables from USOS."""
import re
import usos_tools.login
import usos_tools.timetables as tt
from scripts.utils import get_login_credentials, get_pattern

def main (args):
    credentials = get_login_credentials (args)
    expression = get_pattern (args)

    cookies = usos_tools.login.log_in_to_usos (*credentials)
    for timetable_name, timetable_id in tt.get_all_timetables (cookies):
        if re.match (expression, timetable_name):
            tt.delete_timetable (timetable_id, cookies)
