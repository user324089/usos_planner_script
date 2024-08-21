"""Downloads course data from USOSweb (to later use in judger) and saves it in a JSON file."""
import json
from collections import defaultdict
import usos_tools.login
import usos_tools.courses
from scripts.utils import get_cycle, read_words_from_file

def main(args):
    cycle = get_cycle (args)
    codes = read_words_from_file ('codes')
    if not codes:
        print('No course codes found in file "codes"')
        return
    entries = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for course in codes:
        term = usos_tools.courses.get_course_term(course, cycle)
        course_groups = usos_tools.courses.get_course_groups(course, term, False)
        # iterate over group hours
        for classtype, groups in course_groups[course].items():
            for group in groups:
                for hour in group.hours:
                    relevant_data = {
                        'day': hour.day,
                        'parity': hour.parity,
                        'lesson': int(hour.time_from - 8) // 2,
                        'teacher': group.teacher
                    }
                    # first (only) group num
                    group_num = next(iter(group.group_nums))
                    entries[course][classtype][group_num].append(relevant_data)

    # sort entries by classtype
    for course in entries:
        entries[course] = dict(sorted(entries[course].items()))

    json_str = json.dumps(entries, indent=2)

    with open("site/data.js", 'w', encoding='utf-8') as f:
        f.write ('let data=')
        f.write (json_str)
