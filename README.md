# Reverse engineering the binary save formats of Microsoft BASIC

This repository will be a collection of documents and scripts that help reverse engineering binary save formats of various Microsoft BASIC versions.

## QuickBASIC

The folder `qb` contains the current work for QuickBASIC versions 4.0, 4.5, 7.0, 7.1 as well as Visual Basic for MS-DOS.
It contains `doc.html`, documenting the file format as it is known, and a script `qb.py` that takes as argument the file name of a BASIC file, saved in binary format, and outputs a textual representation.
The output should be as close to the text format saved by QuickBASIC.

## Macintosh BASIC

Unlike the MS-DOS versions, QuickBASIC for Macintosh uses a tokenized file format, similar to GW-BASIC.
Like QuickBASIC, line numbers are optional, and variable names are stored in a table.
The script `mac.py` in the folder `mac` converts a Macintosh binary file into text output.

### Format of QuickBASIC binary files

The first byte is `F1` (hexadecimal) for tokenized files (`F0` for protected files, format unknown).
It is then followed by a series of lines.

Each line starts with a 16-bit big endian word, encoding the length of the line in bytes (including this 16-bit word).
The most significant bit is set if the line starts with a line number.
Then a single byte encodes the number of spaces (one less if it starts with a line number) preceding the first non-space character.
If the line has a line number (that is, the most significant bit of the initial 16-bit word is set), then a 16-bit big endian word follows, storing the number.
The line body then follows as a token stream, with bytes `20` to `7E` (hexadecimal) encoding their ASCII values.
Each line is then terminated by a null byte.

The last line is followed by a 16-bit null word, an impossible byte length for a line (it is always at least 2 bytes long).
Then the section containing identifier names follow.
It always starts on an even address, with a single null byte.
Each identifier begins with a single byte, encoding the length of the identifier, followed by the characters of the identifier.

Identifiers are indexed by their number in the sequence: the first identifier is accessed as identifier 0, the second one as identifier 1, and so on.

For the various token types, see `mac.py` under the `mac` folder.

# Disclaimer

This work is done without any access to disassembly or internal documentation to the BASIC executables.
All information is provided as-is, with no warranty as to its correctness or usability.
However, the author believes the code produces generally correct output.

# Useful links

GW-BASIC, the predecessor to QuickBASIC, uses its own binary format, already documented in other places:
* [Documentation of the binary format](http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html)
* [PC-BASIC documentation of the binary format](http://robhagemans.github.io/pcbasic/doc/2.0/#technical)

