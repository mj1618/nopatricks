from dataclasses import dataclass, astuple
from enum import Enum

class Axis(Enum):
    X = 1
    Y = 2
    Z = 3

@dataclass
class Coord:
    x: int
    y: int
    z: int

    def __add__(self, diff):
        return Coord(self.x + diff.dx, self.y + diff.dy, self.z + diff.dz)

    def __sub__(self, other):
        if isinstance(other, Coord):
            return diff(self.x - other.x, self.y - other.y, self.z - other.z)
        elif isinstance(other, Diff):
            return self + -other

    def __repr__(self):
        return astuple(self).__repr__()
    
    def in_matrix(self, R):
        return self.x>=0 and self.y>=0 and self.z>=0 \
            and self.x<R and self.y<R and self.z<R

    def adjacent(self, R):
        diffs = [
            Diff(1, 0, 0),
            Diff(-1, 0, 0),
            Diff(0, 1, 0),
            Diff(0, -1, 0),
            Diff(0, 0, 1),
            Diff(0, 0, -1),
        ]
        adjs = [self.__add__(d) for d in diffs]
        return [a for a in adjs if a.in_matrix(R)]

# note: don't construct Diff objects directly; use diff() func to get correct subclass
def diff(dx, dy, dz):
    if clen(dx, dy, dz) == 1:
        if mlen(dx, dy, dz) <= 2:
            return NearDiff(dx, dy, dz)
    elif is_lcd(dx, dy, dz):
        m = mlen(dx, dy, dz)
        if m <= 5:
            return ShortDiff(dx, dy, dz)
        elif m <= 15:
            return LongDiff(dx, dy, dz)
        return LinearDiff(dx, dy, dz)
    return Diff(dx, dy, dz)


def is_lcd(dx, dy, dz):
    idx = int(dx!=0)
    idy = int(dy!=0)
    idz = int(dz!=0)
    if idx + idy + idz == 1:
        if idx == 1:
            return Axis.X
        elif idy == 1:
            return Axis.Y
        else: # idz == 1
            return Axis.Z
    return None

def mlen(dx, dy, dz):
    return abs(dx) + abs(dy) + abs(dz)

def clen(dx, dy, dz):
    return max(abs(dx), abs(dy), abs(dz))


@dataclass
class Diff:
    dx: int
    dy: int
    dz: int

    def mlen(self):
        return sum(map(abs, astuple(self)))

    def clen(self):
        return max(map(abs, astuple(self)))

    def __repr__(self):
        return f"<{self.dx}, {self.dy}, {self.dz}>"

# a linear coordinate difference has exactly one non-zero component
class LinearDiff(Diff):
    axis: Axis

    def __init__(self, dx, dy, dz):
        self.axis = is_lcd(dx, dy, dz)
        if self.axis is None:
            raise ValueError(f"invalid lcd: <{dx}, {dy}, {dz}>")
        super().__init__(dx, dy, dz)

    def __neg__(self):
        return LinearDiff(-self.dx, -self.dy, -self.dz)

# ShortDiff is a linear coordinate difference with 0 < mlen <= 5
class ShortDiff(LinearDiff):
    def __init__(self, dx, dy, dz):
        if mlen(dx, dy, dz) > 5:
            raise ValueError(f"invalid sld: <{dx}, {dy}, {dz}>")
        super().__init__(dx, dy, dz)

    def __neg__(self):
        return ShortDiff(-self.dx, -self.dy, -self.dz)

# LongDiff is a linear coordinate difference with 5 < mlen <= 15
class LongDiff(LinearDiff):
    def __init__(self, dx, dy ,dz):
        if mlen(dx, dy, dz) > 15:
            raise ValueError(f"invalid lld: <{dx}, {dy}, {dz}>")
        super().__init__(dx, dy, dz)

    def __neg__(self):
        return LongDiff(-self.dx, -self.dy ,-self.dz)

# NearDiff is a coordinate difference with one or two axes having 1 or -1 and the other 0
class NearDiff(Diff):
    def __init__(self, dx, dy, dz):
        if clen(dx, dy, dz) > 1 or mlen(dx, dy, dz) > 2:
            raise ValueError(f"invalid nd: <{dx}, {dy}, {dz}>")
        self.dx = dx
        self.dy = dy
        self.dz = dz

    def __neg__(self):
        return NearDiff(-self.dx, -self.dy, -self.dz)

@dataclass
class Line:
    c1: Coord
    c2: Coord
    axis: Axis

    def __init__(self, c1, c2):
        diff = c1 - c2
        if not isinstance(diff, LinearDiff):
            raise ValueError(f"invalid line: [{c1}, {c2}]")
        self.c1 = c1
        self.c2 = c2
        self.axis = diff.axis

    def __repr__(self):
        return f"[{self.c1}, {self.c2}]"

    def contains(self, coord):
        def within(val, v1, v2):
            return (min(v1, v2) <= val and val <= max(v1, v2))

        return within(coord.x, self.c1.x, self.c2.x) and within(coord.y, self.c1.y, self.c2.y) and within(coord.z, self.c1.z, self.c2.z)

