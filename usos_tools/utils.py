"""This module contains utility functions and constants used across the package."""
import re
import random

USOSWEB_KONTROLER = 'https://usosweb.mimuw.edu.pl/kontroler.php'
DEFAULT_TIMEOUT = 10

ODD_DAYS = 1
EVEN_DAYS = 2
ALL_DAYS = ODD_DAYS | EVEN_DAYS

def _create_form_str (options: dict[str, str]) -> tuple[str, str]:
    """Creates a multiform post payload and returns it and the boundary."""
    boundary: str = '-' * 27 +  ''.join(random.choices('0123456789', k=20))
    boundary_longer: str = '--' + boundary
    total: str = ''
    for opt in options:
        total += boundary_longer + '\r\n'
        total += 'Content-Disposition: form-data; name="' + opt + '"\r\n\r\n'
        total += options[opt] + '\r\n'
    total += boundary_longer + '--\r\n'
    return total, boundary

def _get_csrf_token(string: str) -> str:
    """Returns the first CSRF token appearing in the string."""
    if match := re.search('csrftoken = "(.*?)"', string):
        return match.group(0)
    raise RuntimeError ('failed to read csrf token')

def _get_weekday_polish(string: str) -> str | None:
    """Returns first weekday (in Polish) appearing in the string."""
    if match := re.search(r'poniedziałek|wtorek|środa|czwartek|piątek', string):
        return match.group(0)
    return None

def _get_parity_polish(string: str) -> str:
    """Returns first parity descriptor (in Polish) appearing in the string."""
    if match := re.search(r'nieparzyste|parzyste|każd', string):
        return match.group(0)
    raise RuntimeError ('failed to read parity')

def _parity_to_int_polish(parity: str) -> int:
    """Converts parity (in Polish) into an int representaion."""
    match parity:
        case 'nieparzyste':
            return ODD_DAYS
        case 'parzyste':
            return EVEN_DAYS
        case 'każd':
            return ALL_DAYS
        case _:
            raise ValueError('parity is wrong')

CLASSTYPES = {
    "Laboratorium": 'LAB',
    "Wykład": 'WYK',
    "Ćwiczenia": 'CW',
    "Wychowanie fizyczne": "WF"
}

def _get_classtype_polish(string: str) -> str:
    """Returns first classtype (in Polish) appearing in the string."""
    pattern = r'(?:' + '|'.join(CLASSTYPES.keys()) + ')'
    if class_type_match := re.search(pattern, string):
        return CLASSTYPES[class_type_match.group(0)]
    return "Unknown classtype"
