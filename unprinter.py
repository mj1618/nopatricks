#!/usr/bin/env python3
import sys

import commands
from mrcrowbar import utils

def unprint(cmds, skip_halt=False):
    
    # so the real trick is keeping track of the fission and fusion commands.
    # when fissioning, the new bot is always added to the end of the buffer for each timestep
    # fusion can merge any two bots, which isn't reversible.
    # this means we have to adjust the order of the bots in the instruction buffer urgh
    # that's not too bad, we don't have to simulate the whole thing, just a wee subset

    """

1 -> 1, 2
1 wait      2 -> 2, 3
1, 2 -> 1   1, 2 -> 1   3 wait
1 wait      3 move
1, 3 -> 1   1, 3 -> 1
    
    """

    # first pass: find out the create/destroy ordering of the bots
    bots = [{'id': 1, 'x': 0, 'y': 0, 'z': 0}]
    bot_acc = 2
    time = 0
    changes = {}
    instructions = iter(cmds)
    end = False
    while not end:
        buffer = [next(instructions) for i in bots]
        splits = []
        merges = []
        new_bots = []
        dead_bots = []
        prims = []
        secs = []
        for i, instr in enumerate(buffer):
            klass = type(instr)
            if klass == commands.Fission:
                splits.append((bots[i]['id'], bot_acc))
                new_bots.append({'id': bot_acc, 'x': bots[i]['x']+instr.ndx, 'y': bots[i]['y']+instr.ndy, 'z': bots[i]['y']+instr.ndy})
                bot_acc += 1
            elif klass == commands.SMove:
                bots[i]['x'] += instr.lldx
                bots[i]['y'] += instr.lldy
                bots[i]['z'] += instr.lldz
            elif klass == commands.LMove:
                bots[i]['x'] += instr.sld1x+instr.sld2x
                bots[i]['y'] += instr.sld1y+instr.sld2y
                bots[i]['z'] += instr.sld1z+instr.sld2z
            elif klass == commands.FusionS:
                dead_bots.append(bots[i])
                secs.append((bots[i]['id'], (bots[i]['x']+instr.ndx, bots[i]['y']+instr.ndy, bots[i]['z']+instr.ndy)))
            elif klass == commands.FusionP:
                prims.append((bots[i]['id'], (bots[i]['x']+instr.ndx, bots[i]['y']+instr.ndy, bots[i]['z']+instr.ndy)))
            elif klass == commands.Halt:
                end = True

        for prim_id, sec_pos in prims:
            for sec_id, prim_pos in secs:
                primbot = next(b for b in bots if b['id'] == prim_id)
                secbot = next(b for b in bots if b['id'] == sec_id)
                if prim_pos == (primbot['x'], primbot['y'], primbot['z']) and sec_pos == (secbot['x'], secbot['y'], secbot['z']):
                    merges.append((prim_id, sec_id))

        bots.extend(new_bots)
        for b in dead_bots:
            bots.remove(b)
        if splits or merges:
            changes[time] = {'splits': splits, 'merges': merges}
        time += 1

    print(changes)

    # create a handy mapping between the current bot order vs the order we want them to appear in
    map_acc = 2
    mapping = {1: 1}
    times = [t for t in changes.keys()]
    times.sort(key=lambda x: -x)
    for ts in times:
        for prim, sec in changes[ts]['merges']:
            if prim not in mapping:
                mapping[prim] = map_acc
                map_acc += 1
            if sec not in mapping:
                mapping[sec] = map_acc
                map_acc += 1

    mapping_rev = {v: k for k, v in mapping.items()}
    print(mapping)



    # second pass: create an inverted copy of all the instructions
    # bots are stored here with the normal unmapped ID
    bots = [{'id': 1, 'x': 0, 'y': 0, 'z': 0}]
    time = 0
    result = []
    if not skip_halt:
        result.append(commands.Halt())
    instructions = iter(cmds)

    end = False
    while not end:
        buffer = [(mapping[b['id']], next(instructions)) for b in bots]
        # replace merges with splits and vice versa
        if time in changes:
            for prim, sec in changes[time]['splits']:
                fiss = buffer.pop(next(i for i, x in enumerate(buffer) if x[0]==mapping[prim]))[1]
                primbot = next(b for b in bots if b['id'] == prim) 
                secbot = {'id': sec, 'x': primbot['x']+fiss.ndx, 'y': primbot['y']+fiss.ndy, 'z': primbot['y']+fiss.ndy}
                bots.append(secbot) 

                buffer.append((mapping[prim], commands.FusionP().set_nd(secbot['x']-primbot['x'], secbot['y']-primbot['y'], secbot['z']-primbot['z']) ))
                buffer.append((mapping[sec], commands.FusionS().set_nd(primbot['x']-secbot['x'], primbot['y']-secbot['y'], primbot['z']-secbot['z']) ))

            for prim, sec in changes[time]['merges']:
                fusp = buffer.pop(next(i for i, x in enumerate(buffer) if x[0]==mapping[prim]))[1]
                fuss = buffer.pop(next(i for i, x in enumerate(buffer) if x[0]==mapping[sec]))[1]
                primbot = next(b for b in bots if b['id'] == prim)
                secbot = next(b for b in bots if b['id'] == sec)

                buffer.append((mapping[prim], commands.Fission().set_nd(fusp.ndx, fusp.ndy, fusp.ndz)))
                bots.remove(secbot)

        # rearrange all the instructions in the buffer based on the new bot order
        buffer.sort(key=lambda x: -x[0])
        
        for bot_id, instr in buffer:
            klass = type(instr)
            # most instructions we can pass through
            if klass in (commands.Wait, commands.Flip):
                result.append(instr)
            # reverse move instructions
            elif klass == commands.SMove:
                bot = next(b for b in bots if b['id'] == mapping_rev[bot_id])
                bot['x'] += instr.lldx
                bot['y'] += instr.lldy
                bot['z'] += instr.lldz
                mod = commands.SMove().set_lld( -instr.lldx, -instr.lldy, -instr.lldz )
                result.append(mod)
            elif klass == commands.LMove:
                bot = next(b for b in bots if b['id'] == mapping_rev[bot_id])
                bot['x'] += instr.sld1x+instr.sld2x
                bot['y'] += instr.sld1y+instr.sld2y
                bot['z'] += instr.sld1z+instr.sld2z
                mod = commands.LMove().set_sld1( -instr.sld2x, -instr.sld2y, -instr.sld2z ).set_sld2( -instr.sld1x, -instr.sld1y, -instr.sld1z )
                result.append(mod)
            # invert fill/void. offset is relative to bot pos, so remains the same
            elif klass == commands.Fill:
                mod = commands.Void().set_nd( instr.ndx, instr.ndy, instr.ndz )
                result.append(mod)
            elif klass == commands.Void:
                mod = commands.Fill().set_nd( instr.ndx, instr.ndy, instr.ndz )
                result.append(mod)
            elif klass == commands.GFill:
                mod = commands.GVoid().set_nd( instr.ndx, instr.ndy, instr.ndz ).set_fd( instr.fdx, instr.fdy, instr.fdz )
            elif klass == commands.GVoid:
                mod = commands.GFill().set_nd( instr.ndx, instr.ndy, instr.ndz ).set_fd( instr.fdx, instr.fdy, instr.fdz )
            elif klass in (commands.Fission, commands.FusionP, commands.FusionS):
                # we've intercepted and modified these in advance
                result.append(instr)

            elif klass == commands.Halt:
                # we've reached the end
                end = True
        
        bots.extend(new_bots)
        for b in dead_bots:
            bots.remove(b)
        time += 1

    return reversed(result)
    
    

if __name__ == '__main__':
    problem = int(sys.argv[1])
    f = open('submission/FA{:03d}.nbt'.format(problem), 'rb').read()
    cmds = commands.read_nbt(f)
    res = unprint(cmds)
    
    data = commands.export_nbt( res )
    g = open('submission/FD{:03d}.nbt'.format(problem), 'wb')
    g.write(data)
    g.close()

