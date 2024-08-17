"""This module contains utility functions and constants used across the package."""
import re
import random
import pathlib
from usos_tools.models import HourEntry, GroupEntry

USOSWEB_KONTROLER_BASE_URL = 'https://usosweb.mimuw.edu.pl/kontroler.php'
USOSAPI_BASE_URL = 'https://usosapps.uw.edu.pl/services'
DEFAULT_TIMEOUT = 20
USOSAPI_TIMEOUT = 10

ODD_DAYS = 1
EVEN_DAYS = 2
ALL_DAYS = ODD_DAYS | EVEN_DAYS

WEEKDAYS_POLISH = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela']

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
    if match := re.search(r'|'.join(WEEKDAYS_POLISH), string):
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

def _transform_time (hours_str: str | int, minutes_str: str | int):
    """Converts time into a decimal,
    adjusting for actual length of the class."""
    hours = int(hours_str)
    minutes = int(minutes_str)
    if minutes == 0 and hours != 10:
        hours -= 1
        minutes = 45
    return hours + minutes/60

def do_hours_collide (l: HourEntry, r: HourEntry) -> bool:
    """Checks if two HourEntries overlap."""
    if l.day != r.day:
        return False
    if l.parity & r.parity == 0:
        return False
    return l.time_from <= r.time_to and l.time_to >= r.time_from

def do_groups_collide (l: GroupEntry, r: GroupEntry) -> bool:
    """Checks if two GroupEntries overlap in time."""
    return any(do_hours_collide(hour_l, hour_r) for hour_l in l.hours for hour_r in r.hours)

def _merge_groups_by_time(groups: list[GroupEntry]) -> list[GroupEntry]:
    """Returns list with groups merged by their hours (all group numbers are in group_nums)."""
    merged_groups: list[GroupEntry] = []
    for group in groups:
        for merged_group in merged_groups:
            if group.hours == merged_group.hours:
                merged_group.group_nums.update(group.group_nums)
                break
        else:
            merged_groups.append(group)
    return merged_groups

# Cache handling #

CACHE_DIR = pathlib.Path(__file__).parent.parent / '.cache_usos_tools'

def _is_file_cached(path: str | pathlib.Path) -> bool:
    """Checks if the file is cached."""
    return (CACHE_DIR / path).resolve().exists()

def _load_cache(path: str | pathlib.Path) -> str:
    """Loads a file from cache. The file must exist."""
    with open((CACHE_DIR / path).resolve(), 'r', encoding='utf-8') as file:
        return file.read()

def _save_cache(path: str | pathlib.Path, data: str):
    """Saves data to cache. Creates the directory if it doesn't exist."""
    full_path = (CACHE_DIR / path).resolve()
    # create the directories if they don't exist
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as file:
        file.write(data)
