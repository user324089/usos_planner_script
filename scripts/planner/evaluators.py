"""
This module contains functions for evaluating timetables.
"""
import json
import pathlib
from collections import defaultdict

import usos_tools.timetables as tt
from usos_tools.utils import EVEN_DAYS, ODD_DAYS


def evaluate_timetable_time(timetable: list[tt.GroupEntry], _: pathlib.Path) -> int:
    """
    Returns timetable badness with regard to the days' length, their start and end.
    :param timetable: list of groups in the timetable
    :param _:
    :return: badness of the timetable
    """

    map_days_to_hours: dict[tuple[str, int], list[tt.HourEntry]] = defaultdict(list[tt.HourEntry])

    for entry in timetable:
        for hour in entry.hours:
            if hour.parity & EVEN_DAYS:
                map_days_to_hours[(hour.day, EVEN_DAYS)].append(hour)
            if hour.parity & ODD_DAYS:
                map_days_to_hours[(hour.day, ODD_DAYS)].append(hour)

    day_lens: list[tuple[int, int]] = []
    for current_hour_list in map_days_to_hours.values():
        to = max(hour.time_to for hour in current_hour_list)
        fro = min(hour.time_from for hour in current_hour_list)
        day_lens.append((fro, to))

    res = 0
    for day_len in day_lens:
        res += 20
        res += day_len[1]-day_len[0]
        if day_len[0] < 10:
            res += 2
        if day_len[1] > 15:
            res += 2
        if day_len[1] > 17:
            res += 10
        if day_len[1] - day_len[0] > 9:
            res += 30
    return res


custom_evaluate_data = {}


def evaluate_timetable_custom(timetable: list[tt.GroupEntry], path: pathlib.Path) -> int:
    """
    Returns the badness of the timetable as a sum of badnesses of individual groups.
    :param timetable: list of groups in the timetable
    :param path: path to the file with group badnesses
    :return: badness of the timetable
    """
    if path in custom_evaluate_data:
        data = custom_evaluate_data[path]
    else:
        with open((path / 'data.json').resolve(), 'r', encoding="utf-8") as data_file:
            data = json.load(data_file)
            custom_evaluate_data[path] = data
    result: int = 0
    for group in timetable:
        values_for_groups = [int(data[group.course][group.classtype][single_group])
                             for single_group in group.group_nums]
        result += min(values_for_groups)

    return result


EVALUATORS = {
    'time': evaluate_timetable_time,
    'custom': evaluate_timetable_custom
}
