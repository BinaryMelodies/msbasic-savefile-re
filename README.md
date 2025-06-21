# Reverse engineering the binary save formats of Microsoft BASIC

This repository will be a collection of documents and scripts that help reverse engineering binary save formats of various Microsoft BASIC versions.

## QuickBASIC

The folder `qb` contains the current work for QuickBASIC versions 4.0, 4.5, 7.0, 7.1 as well as Visual Basic for MS-DOS.
It contains `doc.html`, documenting the file format as it is known, and a script `qb.py` that takes as argument the file name of a BASIC file, saved in binary format, and outputs a textual representation.
The output should be as close to the text format saved by QuickBASIC.

# Disclaimer

This work is done without any access to disassembly or internal documentation to the BASIC executables.
All information is provided as-is, with no warranty as to its correctness or usability.
However, the author believes the code produces generally correct output.

# Useful links

GW-BASIC, the predecessor to QuickBASIC, uses its own binary format, already documented in other places:
* [Documentation of the binary format](http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html)
* [PC-BASIC documentation of the binary format](http://robhagemans.github.io/pcbasic/doc/2.0/#technical)

