"""This module provides functionality to log in to the USOS system."""
import re
import requests
from usos_tools.utils import USOSWEB_KONTROLER_BASE_URL, DEFAULT_TIMEOUT

USOS_LOGIN_URL = 'https://logowanie.uw.edu.pl/cas/login'
def log_in_to_usos (username, password):
    """Logs into USOS and returns cookies with PHP session."""
    r1 = requests.get(
        USOS_LOGIN_URL,
        timeout=DEFAULT_TIMEOUT
    )
    cookies = r1.cookies

    lt = re.findall ('name="lt" value="(.*?)"', r1.text)[0]
    execution = re.findall ('name="execution" value="(.*?)"', r1.text)[0]
    event_id = re.findall ('name="_eventId" value="(.*?)"', r1.text)[0]

    r2 = requests.post(
        USOS_LOGIN_URL,
        data={
            'lt': lt,
            'execution': execution,
            '_eventId': event_id,
            'username': username,
            'password': password,
            'jsessionid': r1.cookies['JSESSIONID']
        },
        cookies=r1.cookies,
        timeout=DEFAULT_TIMEOUT
    )
    cookies.update(r2.cookies)

    r3 = requests.get(
        USOS_LOGIN_URL,
        params={
            'service': USOSWEB_KONTROLER_BASE_URL + '?_action=news/default',
            'gateway': 'true'
        },
        cookies=cookies,
        timeout=DEFAULT_TIMEOUT
    )
    print ('logged in to usos')
    return r3.cookies
