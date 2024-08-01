import re
import sys
import json
import math
import requests
import bs4
from bs4 import BeautifulSoup

ELEMS_PER_PAGE: int = 100

def get_subjects_response (begin: int, count: int) -> requests.Response:
    params = {
            'forward': '',
            '_pattern': '',
            'cp_showDescriptions': 0,
            'cp_showGroupsColumn': 0,
            'cp_cdydsDisplayLevel': 2,
            'f_tylkoWRejestracji': 0,
            'f_obcojezyczne': 0,
            'method': 'default',
            'kierujNaPlanyGrupy': 0,
            'pattern': '',
            'tab7ad4_offset': begin,
            'tab7ad4_limit': count,
            'tab7ad4_order': '2a1a',
            'f_modified': 1,
            'f_grupa': '',
            }

    return requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php?_action=katalog2/przedmioty/szukajPrzedmiotu',
                         params = params, timeout=20)

def download_all_subjects ():

    count_response = get_subjects_response (0,1)
    print ('has count response')
    num_subjects_match  = re.search (r'elements-count=(\d*)', count_response.text)

    if num_subjects_match is None:
        print ('error reading number of subjects')
        sys.exit (1)

    num_subjects: int = int(num_subjects_match[1])

    codes_with_names: list[tuple[str, str]] = []

    for i in range (math.ceil(num_subjects/ELEMS_PER_PAGE)):
        r = get_subjects_response (i*ELEMS_PER_PAGE, ELEMS_PER_PAGE)
        soup = BeautifulSoup (r.content, 'html.parser')

        for tr in soup.find_all('tr', ['odd_row', 'even_row']):
            elems: bs4.ResultSet[bs4.Tag] = tr.find_all ('td')
            code_elem: bs4.Tag = elems[0]
            name_elem: bs4.Tag = elems[1]
            code_matches = re.search (r'\S+', code_elem.text)
            if code_matches is None:
                print ('error reading subject code')
                break
            code: str = code_matches[0]
            name: str = name_elem.find_all('a')[-1].text
            codes_with_names.append ((code, name))

        print ('downloaded', len(codes_with_names), 'entries')

    return codes_with_names


codes_with_names: list[tuple[str, str]] = []
try:
    with open ('subjects.json') as subjects_file:
        codes_with_names = json.load(subjects_file)
except FileNotFoundError:
    try:
        codes_with_names = download_all_subjects()
    except KeyboardInterrupt:
        sys.exit (1)

    with open("subjects.json", 'w') as f:
        json.dump(codes_with_names, f, indent=2)

CODE_BOX_LEN = 20
NAME_BOX_LEN = 100

try:
    while True:
        print ('please enter regular expression to search subjects:')
        pattern: str = input()
        for (code, name) in codes_with_names:
            try:
                if re.match (pattern, name):
                    box_len = max(NAME_BOX_LEN, len(name))
                    print ('┌' + CODE_BOX_LEN * '─' + '┬' + box_len * '─' + '┐')
                    print (('│{:>' + str(CODE_BOX_LEN) + '}│{:>' + str(box_len) + '}│')
                           .format(code, name))
                    print ('└' + CODE_BOX_LEN * '─' + '┴' + box_len * '─' + '┘')
            except re.error:
                print ('error with regular expression')
                break
except KeyboardInterrupt:
    sys.exit (0)
