#! /usr/bin/python3

import os
import struct
import sys

TOKENS = {
	0x11: "0",
	0x12: "1",
	0x13: "2",
	0x14: "3",
	0x15: "4",
	0x16: "5",
	0x17: "6",
	0x18: "7",
	0x19: "8",
	0x1A: "9",

	0x80: "ABS",
	0x81: "ASC",
	0x82: "ATN",
	0x83: "CALL",
	0x84: "CDBL",
	0x85: "CHR$",
	0x86: "CINT",
	0x87: "CLOSE",
	0x88: "COMMON",
	0x89: "COS",
	0x8A: "CVD",
	0x8B: "CVI",
	0x8C: "CVS",
	0x8D: "DATA",
	0x8E: "ELSE", # typically used after ':' symbol; needs 08 afterwards
	0x8F: "EOF",

	0x90: "EXP",
	0x91: "FIELD",
	0x92: "FIX",
	0x93: "FN",
	0x94: "FOR",
	0x95: "GET",
	0x96: "GOSUB",
	0x97: "GOTO",
	0x98: "IF",
	0x99: "INKEY$",
	0x9A: "INPUT",
	0x9B: "INT",
	0x9C: "LEFT$",
	0x9D: "LEN",
	0x9E: "LET",
	0x9F: "LINE",

	#0xA0: undefined,
	0xA1: "LOC",
	0xA2: "LOF",
	0xA3: "LOG",
	0xA4: "LSET",
	0xA5: "MID$",
	0xA6: "MKD$",
	0xA7: "MKI$",
	0xA8: "MKS$",
	0xA9: "NEXT",
	0xAA: "ON",
	0xAB: "OPEN",
	0xAC: "PRINT",
	0xAD: "PUT",
	0xAE: "READ",
	0xAF: "REM",

	0xB0: "RETURN",
	0xB1: "RIGHT$",
	0xB2: "RND",
	0xB3: "RSET",
	0xB4: "SGN",
	0xB5: "SIN",
	0xB6: "SPACE$",
	0xB7: "SQR",
	0xB8: "STR$",
	0xB9: "STRING$",
	0xBA: "TAN",
	#0xBB: undefined,
	0xBC: "VAL",
	0xBD: "WEND",
	0xBE: "WHILE",
	0xBF: "WRITE",

	0xC0: "ELSEIF",
	0xC1: "CLNG",
	0xC2: "CVL",
	0xC3: "MKL$",

	#0xC4-0xE2: undefined,

	0xE3: "STATIC",
	0xE4: "USING",
	0xE5: "TO",
	0xE6: "THEN",
	0xE7: "NOT",
	0xE8: "'", # TODO: not sure what this is
	0xE9: ">",
	0xEA: "=", # assignment or equality
	0xEB: "<",
	0xEC: "+",
	0xED: "-",
	0xEE: "*",
	0xEF: "/",

	0xF0: "^",
	0xF1: "AND",
	0xF2: "OR",
	0xF3: "XOR",
	0xF4: "EQV",
	0xF5: "IMP",
	0xF6: "MOD",
	0xF7: "\\",
	0xF8: {
		#0x00-0x7F: undefined
		0x80: "AUTO",
		0x81: "CHAIN",
		0x82: "CLEAR",
		0x83: "CLS",
		0x84: "CONT",
		0x85: "CSNG",
		0x86: "DATE$",
		0x87: "DEFINT",
		0x88: "DEFSNG",
		0x89: "DEFDBL",
		0x8A: "DEFSTR",
		0x8B: "DEF",
		0x8C: "DELETE",
		0x8D: "DIM",
		0x8E: "EDIT",
		0x8F: "END",

		0x90: "ERASE",
		0x91: "ERL",
		0x92: "ERROR",
		0x93: "ERR",
		0x94: "FILES",
		0x95: "FRE",
		0x96: "HEX$",
		0x97: "INSTR",
		0x98: "KILL",
		0x99: "LIST",
		0x9A: "LLIST",
		0x9B: "LOAD",
		0x9C: "LPOS",
		0x9D: "LPRINT",
		0x9E: "MERGE",
		0x9F: "NAME",

		0xA0: "NEW",
		0xA1: "OCT$",
		0xA2: "OPTION",
		0xA3: "PEEK",
		0xA4: "POKE",
		0xA5: "POS",
		0xA6: "RANDOMIZE",
		0xA7: "RENUM",
		0xA8: "RESTORE",
		0xA9: "RESUME",
		0xAA: "RUN",
		0xAB: "SAVE",
		0xAC: "SHELL",
		0xAD: "STOP",
		0xAE: "SWAP",
		0xAF: "SYSTEM",

		0xB0: "TIME$",
		0xB1: "TRON",
		0xB2: "TROFF",
		0xB3: "VARPTR",
		0xB4: "WIDTH",
		0xB5: "BEEP",
		0xB6: "CIRCLE",
		0xB7: "LCOPY",
		0xB8: "MOUSE",
		0xB9: "POINT",
		0xBA: "PRESET",
		0xBB: "PSET",
		0xBC: "RESET",
		0xBD: "TIMER",
		0xBE: "SUB",
		0xBF: "EXIT",

		0xC0: "SOUND",
		0xC1: "BUTTON",
		0xC2: "MENU",
		0xC3: "WINDOW",
		0xC4: "DIALOG",
		0xC5: "LOCATE",
		0xC6: "CSRLIN",
		0xC7: "LBOUND",
		0xC8: "UBOUND",
		0xC9: "SHARED",
		0xCA: "UCASE$",
		0xCB: "SCROLL",
		0xCC: "LIBRARY",
		0xCD: "CVSBCD",
		0xCE: "CVDBCD",
		0xCF: "MKSBCD$",

		0xD0: "MKDBCD$",
		#0xD1-0xD5: undefined,
		0xD6: "DEFLNG",
		0xD7: "SADD",
		#0xD8: undefined,
		0xD9: "COLOR",
		#0xDA: undefined,
		0xDB: "PALETTE",
		#0xDC: undefined
		0xDD: "CHDIR",
		#0xDE, 0xDF: undefined
		0xE0: "CASE",
		0xE1: "PRINTDIALOG",
		0xE2: "SCROLLBAR",
		0xE3: "SELECT",
		#0xE4-0xFF: undefined
	},
	0xF9: {
		#0x00-0xF1: undefined
		0xF2: "IS",
		0xF3: "ABOUT",
		0xF4: "OFF",
		0xF5: "BREAK",
		0xF6: "WAIT",
		0xF7: "USR",
		0xF8: "TAB",
		0xF9: "STEP",
		0xFA: "SPC",
		0xFB: "OUTPUT",
		0xFC: "BASE",
		0xFD: "AS",
		0xFE: "APPEND",
		0xFF: "ALL",
	},
	0xFA: {
		#0x00-0x7F: undefined
		0x80: "PICTURE",
		0x81: "WAVE",
		0x82: "POKEW",
		0x83: "POKEL",
		0x84: "PEEKW",
		0x85: "PEEKL",
		#0x86-0xFF: undefined
	},
	0xFB: {
		#0x00-0xC7: undefined
		0xC8: "TECALTEXT",
		0xC9: "TEUPDATE",
		0xCA: "TEDEACTIVATE",
		0xCB: "TEACTIVATE",
		0xCC: "TEINSERT",
		0xCD: "TEDELETE",
		0xCE: "TEKEY",
		0xCF: "TESCROLL",

		0xD0: "TESETSELECT",
		0xD1: "TESETTEXT",
		0xD2: "FILLPOLY",
		0xD3: "INVERTPOLY",
		0xD4: "ERASEPOLY",
		0xD5: "PAINTPOLY",
		0xD6: "FRAMEPOLY",
		0xD7: "PTAB",
		0xD8: "FILLARC",
		0xD9: "INVERTARC",
		0xDA: "ERASEARC",
		0xDB: "PAINTARC",
		0xDC: "FRAMEARC",
		0xDD: "FILLROUNDRECT",
		0xDE: "INVERTROUNDRECT",
		0xDF: "ERASEROUNDRECT",

		0xE0: "PAINTROUNDRECT",
		0xE1: "FRAMEROUNDRECT",
		0xE2: "FILLOVAL",
		0xE3: "INVERTOVAL",
		0xE4: "ERASEOVAL",
		0xE5: "PAINTOVAL",
		0xE6: "FRAMEOVAL",
		0xE7: "FILLRECT",
		0xE8: "INVERTRECT",
		0xE9: "ERASERECT",
		0xEA: "PAINTRECT",
		0xEB: "FRAMERECT",
		0xEC: "TEXTSIZE",
		0xED: "TEXTMODE",
		0xEE: "TEXTFACE",
		0xEF: "TEXTFONT",

		0xF0: "LINETO",
		0xF1: "MOVE",
		0xF2: "MOVETO",
		0xF3: "PENNORMAL",
		0xF4: "PENPAT",
		0xF5: "PENMODE",
		0xF6: "PENSIZE",
		0xF7: "GETPEN",
		0xF8: "SHOWPEN",
		0xF9: "HIDEPEN",
		0xFA: "OBSCURECURSOR",
		0xFB: "SHOWCURSOR",
		0xFC: "HIDECURSOR",
		0xFD: "SETCURSOR",
		0xFE: "INITCURSOR",
		0xFF: "BACKPAT",
	},
}

def read8(file):
	return file.read(1)[0]

def read16(file):
	return struct.unpack('>H', file.read(2))[0]

def read32(file):
	return struct.unpack('>I', file.read(4))[0]

def readfloat32(file):
	return struct.unpack('>f', file.read(4))[0]

def readfloat64(file):
	return struct.unpack('>d', file.read(8))[0]

def reads(file):
	length = read8(file)
	return file.read(length).decode()

def main():
	with open(sys.argv[1], 'rb') as file:
		first_byte = read8(file)
		# http://robhagemans.github.io/pcbasic/doc/2.0/#technical
		# https://www.msx.org/wiki/MSX-BASIC_file_formats
		if first_byte == 0xF0:
			print("Protected Macintosh BASIC file, unable to parse", file = sys.stderr)
			exit(1)
		elif first_byte == 0xF1:
			pass
		elif first_byte == 0xFC:
			print("QuickBASIC or Visual Basic for MS-DOS binary file, not supported", file = sys.stderr)
			exit(1)
		elif first_byte == 0xFD:
			print("GW-BASIC memory dump, not supported", file = sys.stderr)
			exit(1)
		elif first_byte == 0xFE:
			print("GW-BASIC protected file or MSX-BASIC memory dump, not supported", file = sys.stderr)
			exit(1)
		elif first_byte == 0xFF:
			print("GW-BASIC or MSX-BASIC tokenized file, not supported", file = sys.stderr)
			exit(1)
		else:
			print("Not a Macintosh BASIC file", file = sys.stderr)
			exit(1)

		file.seek(0, os.SEEK_END)
		file_end = file.tell()
		file.seek(1, os.SEEK_SET)

		variables = []
		while True:
			offset = file.tell()
			length = read16(file)
			length &= 0x7FFF
			if length == 0:
				break
			file.seek(offset + length, os.SEEK_SET)

		if (file.tell() & 1) == 0:
			file.seek(1, os.SEEK_CUR)
		else:
			file.seek(2, os.SEEK_CUR)

		while file.tell() < file_end:
			variables.append(reads(file))

		file.seek(1, os.SEEK_SET)
		while True:
			offset = file.tell()
			length = read16(file)
			lineno = (length & 0x8000) != 0
			length &= 0x7FFF
			if length == 0:
				break
			line = ""
			spaces = read8(file)
			if lineno:
				num = read16(file)
				line += f"{num} "
			line += " " * spaces
			while True:
				data = read8(file)
				if data == 0:
					break
				elif 32 <= data <= 126:
					line += chr(data)
				elif data == 0x01:
					# variable
					num = read16(file)
					if num >= len(variables):
						line += f"[unknown variable {num}]"
					else:
						line += variables[num]
				elif data == 0x02:
					# label definition (should be followed by a ':' symbol)
					num = read16(file)
					if num >= len(variables):
						line += f"[unknown variable {num}]"
					else:
						line += variables[num]
				elif data == 0x03:
					# jump to label???
					num = read32(file)
					if num >= len(variables):
						line += f"[unknown variable {num}]"
					else:
						line += variables[num]
				elif data == 0x08:
					# TODO: no idea what this is, it appears at the end of the line after THEN, and following ELSE and CASE, probably internal
					num = read32(file)
					#line += f"[unknown symbol {data:02X}{num:08X}]"
				elif data == 0x0B:
					num = read16(file)
					line += f"&O{num:o}"
				elif data == 0x0C:
					num = read16(file)
					line += f"&H{num:X}"
				elif data == 0x0E:
					num = read32(file)
					# label number
					line += f"{num}"
				elif data == 0x0F:
					num = read8(file)
					line += f"{num}"
				elif data == 0x1B:
					num = read32(file)
					line += f"&H{num:X}&"
				elif data == 0x1C:
					num = read16(file)
					line += f"{num}"
				elif data == 0x1D:
					num = readfloat32(file)
					line += f"{num}"
				elif data == 0x1E:
					num = read32(file)
					line += f"{num}&"
				elif data == 0x1F:
					num = readfloat64(file)
					line += f"{num}#"
				elif data == 0x8E and line.endswith(':'):
					line = line[:-1] + "ELSE"
				elif data == 0xE8 and line.endswith(':REM'):
					line = line[:-4] + "'"
				elif data == 0xEC and line.endswith('WHILE'):
					pass
				else:
					if data in TOKENS:
						if type(TOKENS[data]) is dict:
							subtokens = TOKENS[data]
							data2 = read8(file)
							if data2 in subtokens:
								line += subtokens[data2]
							else:
								line += f"[unknown symbol {data:02X}{data2:02X}]"
						else:
							line += TOKENS[data]
					else:
						line += f"[unknown symbol {data:02X}]"
			print(line)
			file.seek(offset + length, os.SEEK_SET)

if __name__ == '__main__':
	main()

