#!/usr/bin/env python3
import state
import commands
import coord

import sys

if __name__ == '__main__':
    problem = 1
    if len( sys.argv ) > 1:
        problem = int( sys.argv[1], 0 )
    st = state.State.create(problem=problem)
    st.enable_trace = False
    cmd = commands.read_nbt_iter( open('dfltTracesL/LA{:03d}.nbt'.format(problem), 'rb').read() )
    
    try:
        while cmd:
            for bot in st.bots:
                c = next(cmd)
                klass = type(c)
                if klass == commands.Halt:
                    bot.halt()
                elif klass == commands.Wait:
                    bot.wait()
                elif klass == commands.Flip:
                    bot.flip()
                elif klass == commands.SMove:
                    bot.smove( coord.LongDiff( c.lldx, c.lldy, c.lldz ) )
                elif klass == commands.LMove:
                    bot.lmove( coord.ShortDiff( c.sld1x, c.sld1y, c.sld1z ), coord.ShortDiff( c.sld2x, c.sld2y, c.sld2z ) )
                elif klass == commands.Fission:
                    bot.fission( coord.NearDiff( c.ndx, c.ndy, c.ndz ), c.m )
                elif klass == commands.FusionP:
                    bot.fusionp( coord.NearDiff( c.ndx, c.ndy, c.ndz ) )
                elif klass == commands.FusionS:
                    bot.fusions( coord.NearDiff( c.ndx, c.ndy, c.ndz ) )
                elif klass == commands.Fill:
                    bot.fill( coord.NearDiff( c.ndx, c.ndy, c.ndz ) )
                elif klass == commands.Void:
                    bot.void( coord.NearDiff( c.ndx, c.ndy, c.ndz ) )
#                elif klass == commands.GFill:
#                    bot.gfill( coord.NearDiff( c.ndx, c.ndy, c.ndz ), coord.FarDiff( c.fdx, c.fdy, c.fdz ) )
#                elif klass == commands.GVoid:
#                    bot.gfill( coord.NearDiff( c.ndx, c.ndy, c.ndz ), coord.FarDiff( c.fdx, c.fdy, c.fdz ) )
                else:
                    raise TypeError( 'oh noes a {}'.format( klass ) )
            st.step()
            if st.step_id % 1000 == 0:
                print( st )
    except StopIteration:
        pass
    print( 'all done!' )
    print( st )

    out = open('dfltEnergy/LA{:03d}'.format(problem), 'w')
    out.write(str(st.energy))
    out.close()
