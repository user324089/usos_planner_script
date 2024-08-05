import re
from getpass import getpass
import requests
from bs4 import BeautifulSoup
import bs4

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

def get_all_plans (cookies) -> list[tuple[str, int]]:
    r = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/index'}, cookies=cookies)
    soup = BeautifulSoup (r.content, 'html.parser')
    plans: list [tuple[str, int]] = []
    for tr in soup.find_all ('tr')[:-1]:
        td: bs4.element.Tag = tr.find ('td')
        plan_name = td.text.strip()
        dropdown: bs4.element.Tag = tr.find ('dropdown-menu')
        dropdown_data_plan_id: str | list[str] = dropdown['data-plan-id']
        dropdown_plan_id = int(str(dropdown_data_plan_id))
        plans.append ((plan_name, dropdown_plan_id))
    return plans

def delete_plan (plan_id: int, cookies):
    requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'home/plany/usun', 'plan_id': plan_id}, cookies=cookies)

def main ():
    username: str = input('username:')
    password: str = getpass()
    print ('enter regular expression:')
    expression: str = input()

    cookies = log_in_to_usos (username, password)
    for plan_name, plan_id in get_all_plans (cookies):
        if re.match (expression, plan_name):
            delete_plan (plan_id, cookies)

if __name__ == '__main__':
    main()
