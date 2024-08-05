"""Module that downloads all course info and allows to search it using regular expressions."""
import re
import sys
import json
import math
import requests
from bs4 import BeautifulSoup

ELEMS_PER_PAGE: int = 100
DEFAULT_TIMEOUT = 10
CODE_BOX_LEN = 20
NAME_BOX_LEN = 100

def get_subjects_response (begin: int, count: int) -> requests.Response:
    """Get courses from begin to begin+count from the list of all courses."""
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

    return requests.get (
        'https://usosweb.mimuw.edu.pl/kontroler.php?_action=katalog2/przedmioty/szukajPrzedmiotu',
        params=params,
        timeout=DEFAULT_TIMEOUT
    )

def download_all_subjects ():
    """Download all courses visible in USOS course search."""
    count_response = get_subjects_response (0,1)
    print ('Has count response')
    num_subjects_match = re.search (r'elements-count=(\d*)', count_response.text)

    if num_subjects_match is None:
        raise RuntimeError('Error reading number of subjects')

    num_subjects: int = int(num_subjects_match[1])

    codes_with_names: list[tuple[str, str]] = []

    for page_num in range (math.ceil(num_subjects/ELEMS_PER_PAGE)):
        r = get_subjects_response (page_num*ELEMS_PER_PAGE, ELEMS_PER_PAGE)
        soup = BeautifulSoup (r.content, 'html.parser')

        for tr in soup.find_all('tr', ['odd_row', 'even_row']):
            if len(elems := tr.find_all('td')) < 2:
                raise RuntimeError('Error while downloading courses')
            code_elem, name_elem = elems[:2]
            code_matches = re.search (r'\S+', code_elem.text)
            if code_matches is None:
                raise RuntimeError('Error reading subject code')
            code: str = code_matches[0]
            name: str = name_elem.find_all('a')[-1].text
            codes_with_names.append ((code, name))

        print ('Downloaded', len(codes_with_names), 'entries')

    return codes_with_names

def main() -> int:
    """Search for courses matching the provided regex."""
    codes_with_names: list[tuple[str, str]]
    try:
        with open ('subjects.json', encoding="utf-8") as subjects_file:
            codes_with_names = json.load(subjects_file)
    except FileNotFoundError:
        try:
            codes_with_names = download_all_subjects()
        except KeyboardInterrupt:
            return 1

        with open("subjects.json", 'w', encoding="utf-8") as f:
            json.dump(codes_with_names, f, indent=2)

    try:
        while True:
            pattern: str = input('Please enter regular expression to search subjects:')
            try:
                for (code, name) in codes_with_names:
                    if re.match (pattern, name):
                        box_len = max(NAME_BOX_LEN, len(name))
                        print ('┌' + CODE_BOX_LEN * '─' + '┬' + box_len * '─' + '┐')
                        print (('│{:>' + str(CODE_BOX_LEN) + '}│{:>' + str(box_len) + '}│')
                               .format(code, name))
                        print ('└' + CODE_BOX_LEN * '─' + '┴' + box_len * '─' + '┘')
            except re.error:
                print ('Error with regular expression')
    except KeyboardInterrupt:
        return 0

if __name__ == '__main__':
    sys.exit(main())
