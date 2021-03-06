#!/usr/bin/env python

import argparse
from algorithm_shortest import main
from unprinter import unprint

ARGS = {
    '--source': dict( metavar='FILE', dest='source', type=argparse.FileType( mode='rb' ), help='Source model' ),
    '--target': dict( metavar='FILE', dest='target', type=argparse.FileType( mode='rb' ), help='Target model' ),
    'output':   dict( metavar='OUTPUT', type=argparse.FileType( mode='wb' ), help='Output file for trace' ),
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Run a nanobot construction job' )
    for arg, spec in ARGS.items():
        parser.add_argument( arg, **spec )
    raw_args = parser.parse_args()

    # dumb as rocks method
    source_t = None
    target_t = None

    result = bytearray()

    if raw_args.source:
        source_t, success = main(fileobj=raw_args.source)
        if not success:
            raise RuntimeError('algorithm failed for source model!')
        for instr in unprint(source_t.trace, skip_halt=raw_args.target is not None):
            result.extend(instr.export_data())

    if raw_args.target:
        target_t, success = main(fileobj=raw_args.target)
        if not success:
            raise RuntimeError('algorithm failed for target model!')
        for instr in target_t.trace:
            result.extend(instr.export_data())

    raw_args.output.write(result)

