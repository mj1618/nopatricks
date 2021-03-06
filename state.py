#!/usr/bin/env python3
from coord import Coord, UP
import commands

from mrcrowbar.utils import to_uint64_le, unpack_bits
from collections.abc import Mapping
from textwrap import wrap
import os
import math
from dataclasses import dataclass, field
import numpy as np
from enum import Enum

class Voxel:
    """ Voxel represents mutable location information """

    # current implementation is a bitmask held in an int
    # the first few bits are the filled state
    VOID = 0
    FULL = 1 << 0
    GROUNDED = 1 << 1
    # the model bit is on if this location forms part of the target model
    MODEL = 1 << 2
    # the bot bit is on if this location has a bot at it
    BOT = 1 << 3


    def __init__(self, val):
        self.val = val

    @staticmethod
    def empty(is_model=False):
        """ Initialises an empty voxel which is part of the model or not. """
        if is_model:
            return Voxel(Voxel.MODEL)
        return Voxel(Voxel.VOID)

    # access to state is via functions so the implementation is free to change
    def is_void(self):
        return not (self.is_full() or self.is_bot())

    def is_full(self):
        return self.val & Voxel.FULL

    def is_grounded(self):
        return self.val & Voxel.GROUNDED

    def is_bot(self):
        return self.val & Voxel.BOT

    def is_model(self):
        return self.val & Voxel.MODEL

    def __repr__(self):
        return repr(self.val)


class Matrix(Mapping):
    _nfull = None
    _nmodel = None
    _ngrounded = None
    _bounds = None
    """ Matrix(size=R) initialises an empty matrix
        Matrix(problem=N) loads problem N
        Matrix(filename="foo.mdl") loads model file"""

    def __init__(self, **kwargs):
        self.ungrounded = set()
        self.model_pts = None
        if 'size' in kwargs:
            self.size = kwargs['size']
            self._ndarray = np.zeros(shape=(self.size, self.size, self.size), dtype=np.dtype('u1'))
        elif 'filename' in kwargs:
            self.size, self._ndarray = Matrix._load_file(kwargs['filename'])
        elif 'fileobj' in kwargs:
            self.size, self._ndarray = Matrix._load_fileobj(kwargs['fileobj'])
        else:
            self.size, self._ndarray = Matrix._load_prob(kwargs.get('problem', 1))

    @property
    def bounds(self):
        if not self._bounds:
            mcoords = np.where(self._ndarray & Voxel.MODEL)
            self._bounds = (
                min(mcoords[0]), max(mcoords[0])+1,
                min(mcoords[1]), max(mcoords[1])+1,
                min(mcoords[2]), max(mcoords[2])+1
            )
        return self._bounds

    @property
    def nfull(self):
        if not self._nfull:
            self._nfull = np.count_nonzero(self._ndarray & Voxel.FULL)
        return self._nfull

    @property
    def nmodel(self):
        if not self._nmodel:
            self._nmodel = np.count_nonzero(self._ndarray & Voxel.MODEL)
        return self._nmodel

    @property
    def ngrounded(self):
        if not self._ngrounded:
            self._ngrounded = np.count_nonzero(self._ndarray & Voxel.GROUNDED)
        return self._ngrounded

    @staticmethod
    def _load_prob(num):
        return Matrix._load_file("problemsF/FA%03d_tgt.mdl" % num)

    @staticmethod
    def _load_file(filename):
        with open(filename, 'rb') as fp:
            return Matrix._load_fileobj(fp)

    @staticmethod
    def _load_fileobj(fp):
        bytedata = fp.read()
        size = int(bytedata[0])
        ndarray = np.zeros(shape=(size, size, size), dtype=np.dtype('u1'))
        index = 0
        for byte in bytedata[1:]:
            for bit in to_uint64_le( unpack_bits( byte ) ):
                ndarray.flat[index] = Voxel.empty(bit).val
                index += 1
        return size, ndarray

    def is_valid_point(self, coord):
        return (0 <= coord.x < self.size) and (0 <= coord.y < self.size) and (0 <= coord.z < self.size)

    def coord_index(self, coord):
        if not isinstance(coord, Coord):
            raise TypeError()
        if not self.is_valid_point(coord):
            print("invalid pt: "+str(coord))
        assert self.is_valid_point(coord)
        return (coord.x, coord.y, coord.z)

    def in_range(self, val):
        if isinstance(val, int):
            return val >= 0 and val < self.size
        elif isinstance(val, Coord):
            return self.in_range(val.x) and self.in_range(val.y) and self.in_range(val.z)
        raise TypeError()

    def keys(self):
        # loop over y last so we ascend by default
        for y in range(self.size):
            for x in range(self.size):
                for z in range(self.size):
                    yield Coord(x, y, z)

    def __iter__(self):
        return self.keys()

    def __len__(self):
        return self.size ** 3

    def __getitem__(self, key):
        return Voxel(self._ndarray[self.coord_index(key)])

    def __setitem__(self, key, voxel):
        self._ndarray[self.coord_index(key)] = voxel.val

    def ground_adjacent(self, gc):
        stack = [gc]
        while len(stack) > 0:
            g = stack.pop()
            for v in [x for x in g.adjacent(self.size) if self[x].is_full() and not self[x].is_grounded()]:
                self.set_grounded(v)
                if v in self.ungrounded:
                    self.ungrounded.remove(v)
                stack.append(v)

    def toggle_bot(self, c):
        self._ndarray[(c.x, c.y, c.z)] ^= Voxel.BOT

    def set_grounded(self, c):
        self._ndarray[(c.x, c.y, c.z)] |= Voxel.GROUNDED
        self._ngrounded = None # invalidate cache

    def set_full(self, c1, c2=None):
        # fill a voxel or a region
        if not c2:
            assert not (self._ndarray[(c1.x, c1.y, c1.z)] & Voxel.FULL)
            self._ndarray[(c1.x, c1.y, c1.z)] |= Voxel.FULL
        else:
            pass # todo fill region
        self._nfull = None # invalidate cache

    def set_void(self, c1):
        # void a voxel
        assert (self._ndarray[(c1.x, c1.y, c1.z)] & Voxel.FULL)
        self._ndarray[(c1.x, c1.y, c1.z)] ^= Voxel.FULL

    def would_be_grounded(self, p):
        if self[p].val & Voxel.BOT:
            return False
        return p.y == 0 or len([n for n in p.adjacent(self.size) if self._ndarray[(n.x,n.y,n.z)] & Voxel.GROUNDED]) > 0


    def to_fill(self, limit, r):
        USE_NEW_COORD_FILTER=False
        # numpy hax for more speed
        if USE_NEW_COORD_FILTER:
            cs = np.transpose(np.where(self._ndarray & (Voxel.MODEL | Voxel.BOT)))
            cs[(r["minX"] <= cs[:,0]) & (r["maxX"] > cs[:,0]) & (r["minZ"] <= cs[:,2]) & (r["maxZ"] > cs[:,2])]
        else:
            cs = np.transpose(np.where(self._ndarray == Voxel.MODEL))
            coords = cs
        # sort by column 1 (y) and limit to only limit records before instantiating coord objects
        return [Coord(int(x), int(y), int(z)) for x,y,z in coords[coords[:,1].argsort()][:limit]]

    def fill_next(self, bot=None):
        if bot: # sort coords by distance from bot
            if hasattr(bot, "pcache") and bot.pcache and (bot.pcache["pos"] - bot.pos).mlen() < 5:
                coords = bot.pcache["coords"]
            else:
                coords = self.to_fill(int(self.nmodel / self.size), bot.region)
                coords.sort(key=lambda c: (c-bot.pos).mlen() + abs(c.y) * self.size)
                bot.pcache = {"pos": bot.pos, "coords": coords}
            for c in coords:
                minX = bot.region["minX"]
                maxX = bot.region["maxX"]
                minZ = bot.region["minZ"]
                maxZ = bot.region["maxZ"]
                if minZ <= c.z < maxZ and minX <= c.z < maxX:
                    if self._ndarray[c.x,c.y,c.z] == Voxel.MODEL and self.would_be_grounded(c):
                        return c
            else:
                if bot.pos.y < max([b.pos.y for b in bot.state.bots]):
                    bot.smove(UP)
                bot.pcache = None
                return None
        return coords[0]

    def yplane(self, y):
        """ Returns a view into this matrix at a constant y """
        return MatrixYPlane(self, y=y)

    def __repr__(self):
        return "size: {}, model/full/grounded: {}/{}/{}".format(self.size, self.nmodel, self.nfull, self.ngrounded)


class MatrixYPlane(Mapping):
    def __init__(self, matrix, y):
        self.matrix = matrix
        self.y = y

    def keygen(self, tup):
        return Coord(tup[0], self.y, tup[1])

    def keys(self):
        for u in range(self.matrix.size):
            for v in range(self.matrix.size):
                yield (u, v)

    def __iter__(self):
        return self.keys()

    def __len__(self):
        return self.matrix.size ** 2

    def __getitem__(self, key):
        return self.matrix[self.keygen(key)]

    def __setitem__(self, key, value):
        self.matrix[self.keygen(key)] = value

    def __repr__(self):
        return repr(self.matrix._ndarray[:,self.y,:])

    def adjacent(self, key):
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        candidates = [(key[0] + d[0], key[1] + d[1]) for d in deltas]
        return [n for n in candidates if self.matrix.in_range(self.keygen(n))]

@dataclass
class State(object):
    matrix: Matrix
    bots: list = field(default_factory = list)
    trace: list = field(default_factory = list)
    energy: int = 0
    harmonics: bool = False # True == High, False == Low
    step_id: int = 0
    bots_to_add: list = field(default_factory = list)
    primary_fuse_bots: list = field(default_factory = list)
    secondary_fuse_bots: list = field(default_factory = list)
    default_energy: int = 1
    enable_trace: bool = True
    current_moves: set = field(default_factory = set)

    @property
    def R(self):
        return self.matrix.size

    @property
    def score(self):
        return max(0, self.score_max*(self.default_energy-self.energy)/self.default_energy)

    @property
    def score_max(self):
        return math.log2(self.R)*1000

    @classmethod
    def create(cls, **kwargs):
        self = cls(Matrix(**kwargs))
        bot = Bot(state=self)
        self.matrix.toggle_bot(bot.pos) # enter voxel
        self.bots.append(bot)
        if 'problem' in kwargs:
            test = 'dfltEnergy/LA{:03d}'.format(kwargs['problem'])
            if os.path.isfile(test):
                self.default_energy = int(open(test, 'r').read(), 0)
        return self

    def is_model_finished(self):
        return self.matrix.nfull == self.matrix.nmodel

    def find_bot(self, bid):
        for b in self.bots:
            if b.bid == bid:
                return b
    def step_all(self):
        while self.step():
            pass
    def step(self):
        # print("step")
        self.current_moves=set()
        if len([ bot for bot in self.bots if len(bot.actions) > 0 ]) == 0:
            return False

        for bot in self.bots:
            if len(bot.actions)>0:
                bot.actions.pop(0)()
            else:
                bot._wait()

        if self.harmonics == True:
            self.energy += 30 * self.R * self.R * self.R
        else:
            self.energy += 3 * self.R * self.R * self.R

        self.energy += 20 * len(self.bots)
        self.step_id += 1

        for prim_bot, sec_pos in self.primary_fuse_bots:
            found_fuse = False
            for i, (sec_bot, prim_pos) in enumerate(self.secondary_fuse_bots):
                if prim_bot.pos == prim_pos and sec_bot.pos == sec_pos:
                    self.secondary_fuse_bots.pop(i)
                    prim_bot.seeds.append(sec_bot.bid)
                    prim_bot.seeds.extend(sec_bot.seeds)
                    self.matrix.toggle_bot(sec_bot.pos) # leave voxel
                    self.bots.remove(sec_bot)
                    self.energy -= 24
                    found_fuse=True
                    break
            if not found_fuse:
                raise ValueError( 'missing secondary fusion match for {}'.format(prim_bot.bid) )
        if self.secondary_fuse_bots:
            raise ValueError( 'missing primary fusion match for {}'.format(self.secondary_fuse_bots[0][0].bid) )
        self.primary_fuse_bots.clear()

        self.bots.extend(self.bots_to_add)
        self.bots_to_add.clear()

        return True

    def __repr__(self):
        return 'step_id: {}, bots: {}, energy: {}, matrix: {}'.format(self.step_id, len( self.bots ), self.energy, repr(self.matrix))


def default_seeds():
    return list(range(2,41))

class Actions(Enum):
    HALT = 0


@dataclass
class Bot(object): # nanobot
    state: State
    bid: int = 1
    pos: Coord = Coord(0,0,0)
    seeds: list = field(default_factory = default_seeds)
    actions: list = field(default_factory = list)
    # region contains min/max for all coords
    region: dict = field(default_factory = lambda: {
        "minX": 0,
        "maxX": 1000,
        "minZ": 0,
        "maxZ": 1000
    })

    def __getattr__(self, name):
        if not name.startswith("_") and hasattr(self, "_" + name):
            fn = getattr(self, "_" + name)
            def queuefn(*args, **kwargs):
                self.actions.append(lambda: fn(*args, **kwargs))
            return queuefn
        else:
            raise AttributeError

    def _halt(self):
        if len(self.state.bots) > 1:
            raise Exception("Can't halt with more than one bot")
        self.state.trace.append( commands.Halt() )

    def _wait(self):
        self.state.trace.append( commands.Wait() )
        pass

    def _flip(self):
        self.state.harmonics = not self.state.harmonics
        if self.state.enable_trace:
            self.state.trace.append( commands.Flip() )

    def _smove(self, diff):
        # print("smove")
        dest = self.pos + diff

        if dest in self.state.current_moves:
            self.actions = []
            self._wait()
            return

        if not self.state.matrix[dest].is_void():
            self.actions = []
            self._wait()
            # raise RuntimeError('tried to move to occupied point {} at time {}'.format(dest, self.state.step_id))
        else:
            self.state.current_moves.add(self.pos)
            self.state.current_moves.add(dest)
            self.state.matrix.toggle_bot(self.pos) # leave voxel
            self.state.matrix.toggle_bot(dest) # enter voxel
            self.pos = dest
            self.state.energy += 2 * diff.mlen()
            if self.state.enable_trace:
                self.state.trace.append( commands.SMove().set_lld( diff.dx, diff.dy, diff.dz ) )

    def get_lpath(self, diff1, diff2):
        ps = []

        dir1 = diff1.div(diff1.mlen())
        dir2 = diff2.div(diff2.mlen())

        for i in range(1, diff1.mlen()+1):
            ps.append(self.pos + dir1.mul(i))
        for i in range(1, diff2.mlen()+1):
            ps.append(self.pos + diff1 + dir2.mul(i))
        return ps

    def _lmove(self, diff1, diff2):
        dest = self.pos + diff1 + diff2
        # print("")
        # print(self.pos)
        # print(diff1)
        # print(diff2)
        # print(dest)

        # print("lpath")
        # print(self.pos)
        # print(diff1)
        # print(diff2)
        # print(self.get_lpath(diff1, diff2))
        # print([self.state.matrix[p].is_void() for p in self.get_lpath(diff1, diff2)])
        # print([self.state.matrix[p].val for p in self.get_lpath(diff1, diff2)])
        # print(not all( self.state.matrix[p].is_void() for p in self.get_lpath(diff1, diff2)))

        moves = [p for p in self.get_lpath(diff1, diff2)]

        for m in moves:
            if m in self.state.current_moves:
                print("can't lmvove interference")
                # self._smove(UP.mul(self.bid))
                self.actions = []
                self._wait()
                return


        if not all(self.state.matrix[p].is_void() for p in self.get_lpath(diff1, diff2)):
            self.actions = []
            print("can't lmvove")
            self.actions = []
            # self._smove(UP.mul(self.bid))
            self._wait()
            # raise RuntimeError('tried to move to occupied point {} at time {}'.format(dest, self.state.step_id))
        else:
            self.state.current_moves.add(self.pos)
            self.state.current_moves.update(moves)

            self.state.matrix.toggle_bot(self.pos) # leave voxel
            self.state.matrix.toggle_bot(dest) # enter voxel
            self.pos = dest
            self.state.energy += 2 * (diff1.mlen() + 2 + diff2.mlen())
            if self.state.enable_trace:
                self.state.trace.append( commands.LMove().set_sld1( diff1.dx, diff1.dy, diff1.dz ).set_sld2( diff2.dx, diff2.dy, diff2.dz ) )

    def _fission(self, nd, m):
        f = Bot(self.state, self.seeds[0], self.pos + nd, self.seeds[1:m+2])
        self.state.matrix.toggle_bot(self.pos + nd) # enter voxel
        self.seeds = self.seeds[m+2:]
        self.state.bots_to_add.append(f)
        self.state.energy += 24
        if self.state.enable_trace:
            self.state.trace.append( commands.Fission().set_nd( nd.dx, nd.dy, nd.dz ).set_m( m ) )

    def _fusionp(self, nd):
        # note: energy accounted for in State.step
        self.state.primary_fuse_bots.append((self, self.pos+nd))
        if self.state.enable_trace:
            self.state.trace.append( commands.FusionP().set_nd( nd.dx, nd.dy, nd.dz ) )

    def _fusions(self, nd):
        # note: energy accounted for in State.step
        self.state.secondary_fuse_bots.append((self, self.pos+nd))
        if self.state.enable_trace:
            self.state.trace.append( commands.FusionS().set_nd( nd.dx, nd.dy, nd.dz ) )

    def _fill(self, nd):
        # print("doing fill")
        # print(self.pos)
        # print(nd)

        p = self.pos + nd
        if p in self.state.current_moves:
            self._wait()
            return
        matrix = self.state.matrix
        if matrix[p].is_void():
            if matrix.would_be_grounded(p):
                self.state.matrix.set_grounded(p)
                matrix.ground_adjacent(p)
            elif self.state.harmonics:
                matrix.ungrounded.add(p)
            else:
                self._wait()
                return
                # raise RuntimeError('tried to fill ungrounded point {} at time {}'.format(p, self.state.step_id))
            self.state.current_moves.add(p)
            matrix.set_full(p)

            self.state.energy += 12
        else:
            self.state.energy += 6
        if self.state.enable_trace:
            self.state.trace.append( commands.Fill().set_nd( nd.dx, nd.dy, nd.dz ) )

    def _void(self, nd):
        p = self.pos + nd
        if p in self.state.current_moves:
            self._wait()
            return
        matrix = self.state.matrix
        if matrix[p].is_full():
            matrix.set_void(p)
            self.state.energy -= 12
        else:
            self._wait()
            return
        if self.state.enable_trace:
            self.state.trace.append( commands.Void().set_nd( nd.dx, nd.dy, nd.dz ) )

    def _gfill(self, nd, fd):
        print('FIXME: Bot.gfill()')
        if self.state.enable_trace:
            self.state.trace.append( commands.GFill().set_nd( nd.dx, nd.dy, nd.dz ).set_fd( fd.dx, fd.dy, fd.dz ) )

    def _gvoid(self, nd, fd):
        print('FIXME: Bot.gvoid()')
        if self.state.enable_trace:
            self.state.trace.append( commands.GVoid().set_nd( nd.dx, nd.dy, nd.dz ).set_fd( fd.dx, fd.dy, fd.dz ) )

    def __repr__(self):
        return "Bot: {}, Seeds: {}\n\n{}".format(self.bid, self.seeds, repr(self.state.matrix._ndarray[:, self.pos.y, :]))
