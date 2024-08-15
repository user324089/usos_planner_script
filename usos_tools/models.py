from dataclasses import dataclass, field

@dataclass
class HourEntry:
    """Class representing a single class hour."""
    day: str
    parity: int
    time_from: int
    time_to: int

    def __str__ (self):
        return ('day: ' + self.day + ' parity: ' + str(self.parity)
                + ' from: ' + str(self.time_from) + ' to: ' + str(self.time_to))
    def __eq__(self, other):
        if not isinstance(other, HourEntry):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return (self.day == other.day and self.parity == other.parity
                and self.time_from == other.time_from)
    def __hash__(self):
        return hash((self.day, self.parity, self.time_from, self.time_to))


@dataclass
class GroupEntry:
    """Class representing a class group.
    If multiple groups have the same properties (course, classtype, hours),
    they might be grouped into a single GroupEntry with their numbers in group_nums."""

    group_nums: set[str] = field(default_factory=set)
    course: str = ""
    classtype: str = ""
    hours: set[HourEntry] = field(default_factory=set)
    teacher: str = ""

    def __str__ (self):
        return ('group: ' + str(self.group_nums) +
                ' from ' + self.course + ' ' + self.classtype + '\n' +
                '\n'.join(str(hour) for hour in self.hours))

    def __hash__ (self):
        return hash ((self.course, self.classtype))

    def __eq__ (self, r):
        return (self.course == r.course and
                self.classtype == r.classtype and
                self.group_nums == r.group_nums)
