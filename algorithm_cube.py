#!/usr/bin/env python3
import state
import commands
from coord import Coord, diff, UP, DOWN, LEFT, RIGHT, FORWARD, BACK
import sys, os
import math
from algorithm import *
import numpy as np
from math import floor, ceil, sqrt
import cProfile

def next_best_point(st, bot=None):
    minX = bot.region["minX"]
    maxX = bot.region["maxX"]
    minZ = bot.region["minZ"]
    maxZ = bot.region["maxZ"]
    # print(bot.region)

    for y, x, z in np.transpose(np.where(np.transpose(st.matrix._ndarray, (1, 0, 2)) == state.Voxel.MODEL)):
        if minX <= x < maxX and minZ <= z < maxZ:
            coord = Coord(int(x), int(y), int(z))
            if st.matrix.would_be_grounded(coord):
                # print(coord)
                return coord

    for y, x, z in np.transpose(np.where(np.transpose(st.matrix._ndarray, (1, 0, 2)) == state.Voxel.MODEL)):
        if minX - (maxX-minX)/2 <= x < maxX + (maxX-minX)/2 and minZ - (maxZ-minZ)/2 <= z < maxZ + (maxZ-minZ)/2:
            coord = Coord(int(x), int(y), int(z))
            if st.matrix.would_be_grounded(coord):
                # print(coord)
                return coord

    return None

def dig_mofo(st, bot, pt):
    print("dig dig dig")
    print(bot.pos)
    bot.actions=[]
    print(pt)
    path = None
    
    if path is None:
        start = Coord(st.R-1, pt.y, pt.z)
        path = shortest_path(st, bot, start)
        dir = RIGHT
        n = st.R-pt.x-2
    
    if path is None:
        start = Coord(pt.x, pt.y, 0)
        path = shortest_path(st, bot, start)
        dir = FORWARD
        n = pt.z-1

    if path is None:
        start = Coord(pt.x, pt.y, st.R-1)
        path = shortest_path(st, bot, start)
        dir = BACK
        n = st.R-pt.z-2
    
    if path is None:
        start = Coord(0, pt.y, pt.z)
        path = shortest_path(st, bot, start)
        dir = LEFT
        n = pt.x-1

    if path is not None:
        # print("got path")
        print(path)
        compress(st, bot, path)
    else:
        print("couldn't find path to pt: "+str(start))
    
    for i in range(n):
        bot.smove(dir)
        start += dir
        bot.void(dir)
    bot.fill(dir)
    for i in range(n):
        bot.smove(dir.mul(-1))
        start += dir.mul(-1)
        if st.matrix[start + dir].is_model():
            bot.fill(dir)

    print("finished digging")
    

def solve(st):
    stuck_steps=0
    while not st.is_model_finished():
        stuck_bots=0
        for bot in st.bots:
            if len(bot.actions) > 0:
                continue
            # print(bot)
            # n+=1
            # if n>1000:
            #     return
            # pt = next_best_point(st, bot)
            pt = st.matrix.fill_next(bot)
            # print(bot.pos)
            # print("pt")
            # print(pt)
            # print("")
            if pt is None:
                continue
            else:
                if (pt - bot.pos).mlen() == 1 and pt.y <= bot.pos.y:
                    bot.fill(pt - bot.pos)
                    if st.matrix.nfull % 100 == 0:
                        # print every 100 fills
                        print(st)
                else:
                    found = False
                    for a in pt.adjacent(st.R):
                        if not st.matrix._ndarray[a.x,a.y,a.z] & (state.Voxel.BOT | state.Voxel.FULL):
                            # print("path")
                            path = shortest_path(st, bot, a)
                            # if len(path) > 10:
                            #     print(path)
                            # print([b.pos for b in st.bots])
                            if path is not None:
                                # print("got path")
                                compress(st, bot, path)
                                found=True
                                break
                            elif bot.pos.y < st.R - 1:
                                bot.smove(UP)
                    else:
                        # stuck_steps += 1
                        print("bot at {} can't get to {} (no void adjacent)".format(bot.pos, pt))
                        dig_mofo(st, bot, pt)
                        if stuck_steps > 100:
                            raise ValueError("stuck too long")
                    if not found:
                        stuck_bots += 1
        if any(len(bot.actions)>0 for bot in st.bots):
            # for bot in st.bots:
            #     print(bot.pos)
                # if len(bot.actions)>0:
                #     print(bot.actions[0])
            # print("stepping")
            st.step()

        if stuck_bots == len(st.bots):
            raise ValueError( 'all bots stuck!' )


def shortest_path_algo(st):
    bot = st.bots[0]
    bot.smove(UP)

    st.step_all()

    for i in range(1, 8):
        # print(st.bots[0].seeds)
        sorted(st.bots, key=lambda bot: -len(bot.seeds))[0].fission(FORWARD, 0)
        st.step_all()
        b = st.bots[i]
        for x in range(i*10):
            b.smove(LEFT)
        st.step_all()
    b = st.bots[0]
    
    st.step_all()

    minX, maxX, minY, maxY, minZ, maxZ = st.matrix.bounds
    minX, maxX, minY, maxY, minZ, maxZ = (int(minX), int(maxX), int(minY), int(maxY), int(minZ), int(maxZ))

    if maxX-minX>28 or maxY-minY>28 or maxZ-minZ>28:
        raise Exception("model too big")

    corners = [
        Coord(minX, minY, minZ),
        Coord(maxX, minY, minZ),
        Coord(minX, maxY, minZ),
        Coord(maxX, maxY, minZ),
        Coord(minX, maxY, maxZ),
        Coord(maxX, maxY, maxZ),
        Coord(minX, minY, maxZ),
        Coord(maxX, minY, maxZ),
    ]

    cornersf = [
        Coord(maxX, maxY, maxZ),
        Coord(minX, maxY, maxZ),
        Coord(maxX, minY, maxZ),
        Coord(minX, minY, maxZ),
        Coord(maxX, minY, minZ),
        Coord(minX, minY, minZ),
        Coord(maxX, maxY, minZ),
        Coord(minX, maxY, minZ),
    ]

    near = []
    far=[]
    for i in range(4):
        near.append(corners[i])
        far.append(cornersf[i])
        path = shortest_path(st, st.bots[i], corners[i] + BACK)
        compress(st, st.bots[i], path)
        st.step_all()
    for i in range(4,8):
        near.append(corners[i])
        far.append(cornersf[i])
        path = shortest_path(st, st.bots[i], corners[i] + FORWARD)
        compress(st, st.bots[i], path)
        st.step_all()
        
    st.step_all()


    for i in range(8):
        print(near[i])
        print(near[i]-st.bots[i].pos)
        st.bots[i].gvoid(near[i]-st.bots[i].pos, far[i]-near[i])
    
    st.step_all()

if __name__ == '__main__':
    problem = int(sys.argv[1])
    suffix = ""
    st = state.State.create(problem=problem)
    cProfile.run("shortest_path_algo(st)", sort="cumulative")

    bot = st.bots[0]

    for bot2 in st.bots[1:]:
        for a in bot.pos.adjacent(st.R):
            if st.matrix[a].is_void():
                path = shortest_path(st, bot2, a)
                if path is not None:
                    print("found path")
                    compress(st, bot2, path)
                    break
        st.step_all()
        bot.fusionp(bot2.pos - bot.pos)
        bot2.fusions(bot.pos - bot2.pos)
        st.step_all()

    # shortest_path_algo(st)
    back_to_base(st, bot)
    bot.halt()

    while st.step():
        pass

    print( st )
    print( 'energy: {}, default: {}, score: {:0.3f}/{:0.3f}'.format( st.energy, st.default_energy, st.score, st.score_max ) )
    data = commands.export_nbt( st.trace )
    with open("submission/FD"+str(problem).zfill(3)+suffix+".nbt", "wb") as file:
        file.write(data)
