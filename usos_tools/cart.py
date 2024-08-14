"""Program that downloads the courses that a user is registered to"""
import requests
import bs4
from bs4 import BeautifulSoup
import re
from collections import defaultdict

def get_cart_subject_codes (cookies) -> dict[str, list[str]]:

    cart_page_response = requests.get ('https://usosweb.mimuw.edu.pl/kontroler.php', params={'_action': 'dla_stud/rejestracja/koszyk', 'statystyki': 1}, cookies=cookies)

    cycles: list[str] = re.findall (r'\[\d*[LZ]?\]', cart_page_response.text)

    soup = BeautifulSoup (cart_page_response.content, 'html.parser')

    map_cycle_to_codes: dict[str, list[str]] = defaultdict (list)

    table: bs4.element.Tag
    for cycle, table in zip(cycles, soup.find_all("tbody", {"class": "autostrong"})):
        for tr in table.find_all ('tr', recursive=False):
            span: bs4.element.Tag = tr.find ('span')
            map_cycle_to_codes[cycle].append (span.text)

    return map_cycle_to_codes
