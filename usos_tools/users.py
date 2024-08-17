"""
Module for handling users. It provides functions for fetching and caching users.
"""
import json
import pathlib
import requests
from usos_tools.utils import (USOSAPI_TIMEOUT, USOSAPI_BASE_URL)
from usos_tools.utils import _is_file_cached, _save_cache, _load_cache

LOCAL_CACHE_DIR = pathlib.Path('users')
USER_IDS_FILENAME = pathlib.Path('user_ids.json')
USER_IDS_BACKUP_FILENAME = pathlib.Path('user_ids_backup.json')

def get_course_lecturers(course: str, term: str, user_ids: list[str]) -> dict[str: tuple[str, str]]:
    """
    Get lecturers' names for the course. If not all user_ids are found in the cache,
    fetch them from the API. Cache the results. Not all lecturers may be found (and returned).
    :param course: course id
    :param term: course term (edition)
    :param user_ids: list of user ids
    :return: dict with user ids as keys and tuples of first and last names as values
    """
    # try to retrieve all users from the cache
    if len(users := get_users(user_ids)) == len(user_ids):
        return users

    # get all course unit ids in the course
    response = requests.get(
        USOSAPI_BASE_URL + '/courses/course_edition2',
        params={
            'course_id': course,
            'term_id': term,
            'fields': 'course_units'
        },
        timeout=USOSAPI_TIMEOUT
    )
    response.raise_for_status()
    course_units = [unit["id"] for unit in response.json()["course_units"]]

    # get all lecturers for the course units
    users = {}
    for course_unit in course_units:
        response = requests.get(
            USOSAPI_BASE_URL + '/courses/unit',
            params={
                'unit_id': course_unit,
                'fields': 'groups[lecturers]'
            },
            timeout=USOSAPI_TIMEOUT
        )
        response.raise_for_status()

        groups = response.json()["groups"]
        users.update({lecturer["id"]: (lecturer["first_name"], lecturer["last_name"])
                             for group in groups for lecturer in group["lecturers"]})
    _cache_users(users)
    return get_users(user_ids)


def _cache_users(new_users: dict[str: tuple[str, str]]) -> None:
    """
    Add new users to the cache.
    :param new_users: dict with user ids as keys and tuples of first and last names as values
    :return: None
    """
    users = {}
    if _is_file_cached(LOCAL_CACHE_DIR / USER_IDS_FILENAME):
        users = json.loads(_load_cache(LOCAL_CACHE_DIR / USER_IDS_FILENAME))
    elif _is_file_cached(LOCAL_CACHE_DIR / USER_IDS_BACKUP_FILENAME):
        users = json.loads(_load_cache(LOCAL_CACHE_DIR / USER_IDS_BACKUP_FILENAME))

    users.update(new_users)
    users_json = json.dumps(users, indent=1)
    _save_cache(LOCAL_CACHE_DIR / USER_IDS_FILENAME, users_json)
    _save_cache(LOCAL_CACHE_DIR / USER_IDS_BACKUP_FILENAME, users_json)


def get_users(user_ids: list[str]) -> dict[str, tuple[str, str]]:
    """
    Get users from the cache.
    :param user_ids: list of user ids to be retrieved
    :return: dict with user ids as keys and tuples of first and last names as values
    """
    users = {}
    if _is_file_cached(LOCAL_CACHE_DIR / USER_IDS_FILENAME):
        all_users = json.loads(_load_cache(LOCAL_CACHE_DIR / USER_IDS_FILENAME))
        # get all user ids that are in the list
        users = {user_id: all_users[user_id] for user_id in user_ids if user_id in all_users}
    return users
