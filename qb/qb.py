#! /usr/bin/python3

import os
import struct
import sys

import traceback

def read8(file):
	return struct.unpack('<B', file.read(1))[0]

def read16(file):
	return struct.unpack('<H', file.read(2))[0]

def read32(file):
	return struct.unpack('<I', file.read(4))[0]

def read64(file):
	return struct.unpack('<Q', file.read(8))[0]

def readf32(file):
	return struct.unpack('<f', file.read(4))[0]

def readf64(file):
	return struct.unpack('<d', file.read(8))[0]

def reads(file):
	length = read16(file)
	text = file.read(length)
	if (length & 1) != 0:
		file.read(1)
	return text

class Missing:
	pass

Missing = Missing()

def clear_missing(stack_args):
	# required for a few opcodes: CLEAR ...
	args = []
	for arg in stack_args:
		if arg is Missing:
			pass
		else:
			args.append(arg)
	return args

def replace_missing(stack_args):
	# required for a few opcodes: PAINT ...
	args = []
	for arg in stack_args:
		if arg is Missing:
			args.append(None)
		else:
			args.append(arg)
	return args

class Element:
	def __repr__(self):
		return self.__class__.__name__ + repr(self.__dict__)

#### Data types

class AnyType(Element):
	def get_name(self):
		return "ANY"

	def get_short_name(self):
		raise Exception("Any-type has no short form")

	def get_suffix(self):
		raise Exception("Any-type has no type suffix")

class IntegerType(Element):
	def get_name(self):
		return "INTEGER"

	def get_short_name(self):
		return "INT"

	def get_suffix(self):
		return "%"

class LongType(Element):
	def get_name(self):
		return "LONG"

	def get_short_name(self):
		return "LNG"

	def get_suffix(self):
		return "&"

class SingleType(Element):
	def get_name(self):
		return "SINGLE"

	def get_short_name(self):
		return "SNG"

	def get_suffix(self):
		return "!"

class DoubleType(Element):
	def get_name(self):
		return "DOUBLE"

	def get_short_name(self):
		return "DBL"

	def get_suffix(self):
		return "#"

class CurrencyType(Element):
	def get_name(self):
		return "CURRENCY"

	def get_short_name(self):
		return "CUR"

	def get_suffix(self):
		return "@"

class StringType(Element):
	def get_name(self):
		return "STRING"

	def get_short_name(self):
		return "STR"

	def get_suffix(self):
		return "$"

class FixedStringType(Element):
	def __init__(self, count):
		assert type(count) is int
		self.count = count

	def get_name(self):
		return f"STRING * {self.count}"

	def get_short_name(self):
		raise Exception("Fixed string has no short form")

	def get_suffix(self):
		raise Exception("Fixed string has no type suffix")

class CustomType(Element):
	def __init__(self, name):
		self.name = name

	def get_name(self):
		return self.name.print()

	def get_short_name(self):
		raise Exception("Custom type has no short form")

	def get_suffix(self):
		raise Exception("Custom type has no type suffix")

#### Syntactic elements

class Identifier(Element):
	def __init__(self, name, offset, suffix = None):
		assert type(name) in {bytes, int}
		assert type(offset) is int
		assert suffix is None or type(suffix) in {IntegerType, LongType, SingleType, DoubleType, CurrencyType, StringType}
		try:
			name = int(name)
		except ValueError:
			pass
		self.is_number = type(name) is int
		assert type(name) is not int or name >= 0
		if type(name) is int:
			assert suffix is None
		if type(name) is int and name >= 65530:
			name = str(name).encode()
		self.name = name
		self.offset = offset
		self.suffix = suffix

	def print(self, **kwds):
		if type(self.name) is int:
			return str(self.name)
		else:
			return self.name.decode('cp437') + (self.suffix.get_suffix() if self.suffix is not None else "")

class ExternalObject(Element):
	# VBDOS
	def __init__(self, name):
		self.name = name

	def print(self, **kwds):
		return self.name.print(**kwds)

class ArrayElement(Element):
	def __init__(self, name, *args, implicit_dims = False):
		if implicit_dims:
			assert len(args) == 0
			self.args = None
		else:
			self.args = list(args)
		self.name = name

	def print(self, **kwds):
		return self.name.print(**kwds) + ("(" + ", ".join(arg.print(**kwds) for arg in self.args) + ")" if self.args is not None else "")

class FieldSelection(Element):
	def __init__(self, arg, field):
		self.arg = arg
		self.field = field

	def print(self, **kwds):
		return self.arg.print(**kwds) + "." + self.field.print(**kwds)

class DecimalInteger(Element):
	def __init__(self, value, suffix = None):
		assert type(value) is int
		self.value = value
		self.suffix = suffix

	def print(self, **kwds):
		return str(self.value) + (self.suffix if self.suffix is not None else "")

class OctalInteger(Element):
	def __init__(self, value, suffix = None):
		assert type(value) is int
		self.value = value
		self.suffix = suffix

	def print(self, **kwds):
		return f"&O{self.value:o}" + (self.suffix if self.suffix is not None else "")

class HexadecimalInteger(Element):
	def __init__(self, value, suffix = None):
		assert type(value) is int
		self.value = value
		self.suffix = suffix

	def print(self, **kwds):
		return f"&H{self.value:X}" + (self.suffix if self.suffix is not None else "")

class FloatLiteral(Element):
	def __init__(self, value, suffix = None):
		assert type(value) is float
		self.value = value
		self.suffix = suffix

	def print(self, **kwds):
		text = str(self.value).upper()
		if text.endswith('.0'):
			text = text[:-2]
		if text.startswith('0.'):
			text = text[1:]
		if self.suffix == '#' and 'E' in text:
			return text.replace('E', 'D')
		elif self.suffix == '!' and ('.' in text or 'E' in text):
			return text
		else:
			return text + self.suffix

class CurrencyLiteral(Element):
	def __init__(self, value):
		assert type(value) is int
		self.value = value

	def print(self, **kwds):
		text = f'{self.value:05d}'
		text = text[:-4] + '.' + text[-4:]
		text = text.rstrip('0').rstrip('.')
		return text + '@'

class StringLiteral(Element):
	def __init__(self, text):
		self.text = text

	def print(self, **kwds):
		return '"' + self.text.decode('cp437') + '"'

class IncludeText(Element):
	# used for $INCLUDE
	def __init__(self, text):
		self.text = text

	def print(self, **kwds):
		return "'" + self.text.decode('cp437') + "'"

class Parentheses(Element):
	def __init__(self, argument):
		self.argument = argument

	def print(self, **kwds):
		return "(" + self.argument.print(**kwds) + ")"

class UnaryOperator(Element):
	def __init__(self, operator, argument):
		self.operator = operator
		self.argument = argument

	def print(self, **kwds):
		return self.operator + (" " if self.operator != '-' else "") + self.argument.print(**kwds)

class BinaryOperator(Element):
	def __init__(self, operator, argument1, argument2):
		self.operator = operator
		self.arguments = [argument1, argument2]

	def print(self, **kwds):
		return self.arguments[0].print(**kwds) + " " + self.operator + " " + self.arguments[1].print(**kwds)

class TypeOfIsOperator(Element):
	# VBDOS
	def __init__(self, argument, typename):
		self.argument = argument
		self.typename = typename

	def print(self, **kwds):
		return "TYPEOF " + self.argument.print(**kwds) + " IS " + self.typename.print(**kwds)

class MethodSubCall(Element):
	# VBDOS
	def __init__(self, target, name, *args):
		self.target = target
		self.name = name
		self.args = list(args)

	def print(self, **kwds):
		args = [arg.print(**kwds) if arg is not None else "" for arg in self.args]
		return self.target.print(**kwds) + "." + self.name + (" " + ", ".join(arg.print(**kwds) for arg in args) if len(args) > 0 else "")

class MethodFunctionCall(Element):
	# VBDOS
	def __init__(self, target, name, *args):
		self.target = target
		self.name = name
		self.args = list(args)

	def print(self, **kwds):
		args = [arg.print(**kwds) if arg is not None else "" for arg in self.args]
		return self.target.print(**kwds) + "." + self.name + "(" + ", ".join(arg.print(**kwds) for arg in args) + ")"

class BuiltinFunctionCall(Element):
	def __init__(self, name, *args, implicit_args = False):
		if implicit_args:
			assert len(args) == 0
			self.args = None
		else:
			self.args = list(args)
		self.name = name

	def print(self, **kwds):
		text = self.name
		if self.args is not None:
			args = [arg.print(**kwds) if arg is not None else "" for arg in self.args]
			while len(args) > 0 and args[-1] == "":
				args.pop()
			text += "(" + ", ".join(args) + ")"
		return text

class ConvertFunction(Element):
	def __init__(self, arg, dtype):
		self.arg = arg
		self.dtype = dtype

	def print(self, **kwds):
		return "C" + self.dtype.get_short_name() + "(" + self.arg.print(**kwds) + ")"

class ByValue(Element):
	def __init__(self, parameter):
		self.parameter = parameter

	def print(self, **kwds):
		return "BYVAL " + self.parameter.print(**kwds)

class AsSegmented(Element):
	def __init__(self, parameter):
		self.parameter = parameter

	def print(self, **kwds):
		return "SEG " + self.parameter.print(**kwds)

class FileNumber(Element):
	def __init__(self, value):
		self.value = value

	def print(self, **kwds):
		return "#" + self.value.print(**kwds)

class EventSpecification(Element):
	def __init__(self, name, value = None):
		self.name = name
		self.value = value

	def print(self, **kwds):
		return self.name + ("(" + self.value.print(**kwds) + ")" if self.value is not None else "")

class CoordinatePair(Element):
	def __init__(self, x, y, step = False):
		self.x = x
		self.y = y
		self.step = step

	def print(self, **kwds):
		return ("STEP" if self.step else "") + "(" + self.x.print(**kwds) + ", " + self.y.print(**kwds) + ")"

class MetaCommand(Element):
	# appears inside a BASIC comment
	def __init__(self, keyword, argument = None, argument_takes_colon = True):
		self.keyword = keyword
		self.argument = argument
		self.argument_takes_colon = argument_takes_colon

	def print(self, **kwds):
		return self.keyword + ((": " if self.argument_takes_colon else " ") + self.argument.print(**kwds) if self.argument is not None else "")

class EmptyStatement(Element):
	def print(self, **kwds):
		return ""

class RemStatement(Element):
	def __init__(self, text, metacommand = None):
		self.text = text
		self.metacommand = metacommand

	def print(self, **kwds):
		return "REM" + self.text.decode('cp437') + (self.metacommand.print(**kwds) if self.metacommand is not None else "")

class BuiltinStatement(Element):
	def __init__(self, name, *args):
		self.name = name
		self.args = list(args)

	def print(self, **kwds):
		args = [arg.print(**kwds) if arg is not None else "" for arg in self.args]
		while len(args) > 0 and args[-1] == "":
			args.pop()
		return self.name + (" " + ", ".join(args) if len(args) > 0 else "")

class CallStatement(Element):
	def __init__(self, name, *args, explicit = False):
		self.name = name
		self.args = list(args)
		self.explicit = explicit

	def print(self, **kwds):
		if self.explicit:
			return "CALL " + self.name.print(**kwds) + ("(" + ", ".join(arg.print(**kwds) for arg in self.args) + ")" if len(self.args) > 0 else "")
		else:
	 		return self.name.print(**kwds) + (" " + ", ".join(arg.print(**kwds) for arg in self.args) if len(self.args) > 0 else "")

class CallsStatement(Element):
	def __init__(self, name, *args):
		self.name = name
		self.args = list(args)

	def print(self, **kwds):
		return "CALLS " + self.name.print(**kwds) + ("(" + ", ".join(arg.print(**kwds) for arg in self.args) + ")" if len(self.args) > 0 else "")

class AssignmentStatement(Element):
	def __init__(self, target, value, keyword = None):
		self.target = target
		self.value = value
		self.keyword = keyword

	def print(self, **kwds):
		return (self.keyword + " " if self.keyword is not None else "") + self.target.print(**kwds) + " = " + self.value.print(**kwds)

class CircleStatement(Element):
	def __init__(self, center, radius, color = None, start = None, end = None, aspect = None):
		assert isinstance(center, CoordinatePair)
		assert radius is not None
		self.center = center
		self.radius = radius
		self.color = color
		self.start = start
		self.end = end
		self.aspect = aspect

	def print(self, **kwds):
		line = "CIRCLE " + self.center.print(**kwds) + ", " + self.radius.print(**kwds)
		args = [self.color, self.start, self.end, self.aspect]
		while len(args) > 0 and args[-1] is None:
			args.pop()
		args = ", ".join(arg.print(**kwds) if arg is not None else "" for arg in args)
		if args != "":
			line += ", " + args
		return line

class LockStatement(Element):
	def __init__(self, file, start = None, end = None, unlock = False):
		self.file = file
		self.start = start
		self.end = end
		self.unlock = unlock

	def print(self, **kwds):
		return ("UNLOCK " if self.unlock else "LOCK ") + self.file.print(**kwds) + (", " + (self.start.print(**kwds) if self.start is not None else "") + (" " if self.start is not None and self.end is not None else "") + ("TO " + self.end.print(**kwds) if self.end is not None else "") if self.start is not None or self.end is not None else "")

class GetStatement(Element):
	# graphical get statement, I/O get statements are builtins
	def __init__(self, _from, to, arrayspec):
		self._from = _from
		self.to = to
		self.arrayspec = arrayspec

	def print(self, **kwds):
		return "GET " + self._from.print(**kwds) + "-" + self.to.print(**kwds) + ", " + self.arrayspec.print(**kwds)

class PutStatement(Element):
	# graphical put statement, I/O get statements are builtins
	def __init__(self, _from, arrayspec, method = None):
		self._from = _from
		self.arrayspec = arrayspec
		self.method = method

	def print(self, **kwds):
		return "PUT " + self._from.print(**kwds) + ", " + self.arrayspec.print(**kwds) + (", " + self.method if self.method is not None else "")

class LineStatement(Element):
	def __init__(self, _from, to, color, mode, style):
		self._from = _from
		self.to = to
		self.color = color
		self.mode = mode
		self.style = style

	def print(self, **kwds):
		line = "LINE " + (self._from.print(**kwds) if self._from is not None else "") + "-" + self.to.print(**kwds)
		args = [self.color, self.mode, self.style]
		while len(args) > 0 and (args[-1] is None or args[-1] == ""):
			args.pop()
		args = ", ".join("" if arg is None else arg if type(arg) is str else arg.print(**kwds) for arg in args)
		if args != "":
			line += ", " + args
		return line

class KeyStatement(Element):
	def __init__(self, mode):
		self.mode = mode

	def print(self, **kwds):
		return "KEY " + self.mode

class PaintStatement(Element):
	def __init__(self, point, paint = None, border = None, background = None):
		self.point = point
		self.paint = paint
		self.border = border
		self.background = background

	def print(self, **kwds):
		line = "PAINT " + self.point.print(**kwds)
		args = [self.paint, self.border, self.background]
		while len(args) > 0 and args[-1] is None:
			args.pop()
		args = ", ".join(arg.print(**kwds) if arg is not None else "" for arg in args)
		if args != "":
			line += ", " + args
		return line

class PSetStatement(Element):
	def __init__(self, coordinates, color = None, keyword = 'PSET'):
		self.coordinates = coordinates
		self.color = color
		self.keyword = keyword

	def print(self, **kwds):
		return self.keyword + " " + self.coordinates.print(**kwds) + (", " + self.color.print(**kwds) if self.color is not None else "")

class ViewStatement(Element):
	def __init__(self, _from, to, color = None, border = None, keyword = 'VIEW'):
		self._from = _from
		self.to = to
		self.color = color
		self.border = border
		self.keyword = keyword

	def print(self, **kwds):
		args = [
			"(" + self._from[0].print(**kwds) + ", " + self._from[1].print(**kwds) + ")-(" + self.to[0].print(**kwds) + ", " + self.to[1].print(**kwds) + ")",
			self.color.print(**kwds) if self.color is not None else "",
			self.border.print(**kwds) if self.border is not None else ""
		]
		while args[-1] == "":
			args.pop()
		return self.keyword + " " + ", ".join(args)

class ViewPrintStatement(Element):
	def __init__(self, _from = None, to = None):
		self._from = _from
		self.to = to

	def print(self, **kwds):
		return "VIEW PRINT" + (" " + self._from.print(**kwds) + " TO " + self.to.print(**kwds) if (self._from) is not None else "")

class WindowStatement(Element):
	def __init__(self, _from, to, keyword = 'WINDOW'):
		self._from = _from
		self.to = to
		self.keyword = keyword

	def print(self, **kwds):
		return self.keyword + " (" + self._from[0].print(**kwds) + ", " + self._from[1].print(**kwds) + ")-(" + self.to[0].print(**kwds) + ", " + self.to[1].print(**kwds) + ")"

class FieldAssociation(Element):
	def __init__(self, width, var):
		self.width = width
		self.var = var

	def print(self, **kwds):
		return self.width.print(**kwds) + " AS " + self.var.print(**kwds)

class FieldStatement(Element):
	def __init__(self, filenumber, *associations):
		self.filenumber = filenumber
		self.associations = list(associations)

	def print(self, **kwds):
		return "FIELD " + self.filenumber.print(**kwds) + ", " + ", ".join(association.print(**kwds) for association in self.associations)

class NameStatement(Element):
	def __init__(self, oldname, newname):
		self.oldname = oldname
		self.newname = newname

	def print(self, **kwds):
		return "NAME " + self.oldname.print(**kwds) + " AS " + self.newname.print(**kwds)

class InputStatement(Element):
	def __init__(self, *arguments, specification = None, starts_with_semicolon = False, follows_with_comma = False):
		self.kind = None
		self.specification = specification
		self.starts_with_semicolon = starts_with_semicolon
		self.follows_with_comma = follows_with_comma
		self.arguments = list(arguments)

	def print(self, **kwds):
		return self.kind + (" ;" if self.starts_with_semicolon else "") + (" " + self.specification.print(**kwds) + ("," if self.follows_with_comma else ";") if self.specification is not None else "") + " " + ", ".join(argument.print(**kwds) for argument in self.arguments)

class UsingClause(Element):
	def __init__(self, value):
		self.value = value

	def print(self, **kwds):
		return "USING " + self.value.print(**kwds) + ";"

class PrintItem(Element):
	def __init__(self, value = None, separator = ';'):
		self.value = value
		self.separator = separator

	def print(self, **kwds):
		return (self.value.print(**kwds) if self.value is not None else "") + self.separator

class PrintControl(Element):
	def __init__(self, mode, value):
		self.mode = mode
		self.value = value

	def print(self, **kwds):
		return self.mode + "(" + self.value.print(**kwds) + ");"

class PrintStatement(Element):
	def __init__(self, kind = 'PRINT', target = None):
		assert kind in {'PRINT', 'LPRINT', 'WRITE'}
		self.target = target # VBDOS
		self.filenumber = None
		self.kind = kind
		self.items = []

	def add_item(self, item):
		self.items.append(item)

	def add_filenumber(self, filenumber):
		self.filenumber = filenumber

	def print(self, **kwds):
		if self.target is not None:
			text = self.target.print(**kwds) + "." + self.kind
		else:
			text = self.kind
		if len(self.items) > 0:
			text += " " + (self.filenumber.print(**kwds) + ", " if self.filenumber is not None else "")
			args = []
			for item_index, item in enumerate(self.items):
				if item_index > 0 and isinstance(self.items[item_index - 1], PrintControl) and isinstance(item, PrintItem) and item.value is None:
					continue
				args.append(item.print(**kwds))
			text += " ".join(args)
		return text

class OpenStatement(Element):
	# this is only for the OPEN/FOR/AS statement
	def __init__(self, filename, filenumber, mode, access, lock, length = None):
		self.filename = filename
		self.filenumber = filenumber
		self.mode = mode
		self.access = access
		self.lock = lock
		self.length = length

	def print(self, **kwds):
		return "OPEN " + self.filename.print(**kwds) + " FOR " + self.mode + (" ACCESS " + self.access if self.access is not None else "") + (" SHARED" if self.lock == 'SHARED' else " LOCK " + self.lock if self.lock is not None else "") + " AS " + self.filenumber.print(**kwds) + (" LEN = " + self.length.print(**kwds) if self.length is not None else "")

class OpenIsamStatement(Element):
	# QB70+
	def __init__(self, filename, typename, tablename, filenumber):
		self.filename = filename
		self.typename = typename
		self.tablename = tablename
		self.filenumber = filenumber

	def print(self, **kwds):
		return "OPEN " + self.filename.print(**kwds) + " FOR ISAM " + self.typename.print(**kwds) + " " + self.tablename.print(**kwds) + " AS " + self.filenumber.print(**kwds)

class ExitStatement(Element):
	def __init__(self, kind):
		assert kind in {'DEF', 'DO', 'FOR', 'FUNCTION', 'SUB'}
		self.kind = kind

	def print(self, **kwds):
		return "EXIT " + self.kind

class GosubStatement(Element):
	def __init__(self, target):
		self.target = target

	def print(self, **kwds):
		return "GOSUB " + self.target.print(**kwds)

class GotoStatement(Element):
	def __init__(self, target, implicit = False):
		self.target = target
		self.implicit = implicit

	def print(self, **kwds):
		return ("GOTO " if not self.implicit else "") + self.target.print(**kwds)

class ReturnStatement(Element):
	def __init__(self, target = None):
		self.target = target

	def print(self, **kwds):
		return "RETURN" + (" " + self.target.print(**kwds) if self.target is not None else "")

class RestoreStatement(Element):
	def __init__(self, target = None):
		self.target = target

	def print(self, **kwds):
		return "RESTORE" + (" " + self.target.print(**kwds) if self.target is not None else "")

class ResumeStatement(Element):
	def __init__(self, target = Missing):
		self.target = target

	def print(self, **kwds):
		return "RESUME" + ("" if self.target is Missing else " " + self.target.print(**kwds) if self.target is not None else " NEXT")

class RunStatement(Element):
	def __init__(self, target = None):
		self.target = target

	def print(self, **kwds):
		return "RUN" + (" " + self.target.print(**kwds) if self.target is not None else "")

class EventStatement(Element):
	def __init__(self, event, state):
		assert state in {'OFF', 'ON', 'STOP'}
		self.event = event
		self.state = state

	def print(self, **kwds):
		return (self.event.print(**kwds) if self.event is not None else "EVENT") + " " + self.state

class EraseStatement(Element):
	def __init__(self, *arguments):
		self.arguments = list(arguments)

	def print(self, **kwds):
		return "ERASE " + ", ".join(argument.print(**kwds) for argument in self.arguments)

class ReadStatement(Element):
	def __init__(self, *variables):
		self.variables = list(variables)

	def print(self, **kwds):
		return "READ " + ", ".join(variable.print(**kwds) for variable in self.variables)

class OnErrorGotoStatement(Element):
	def __init__(self, target, local = False):
		self.target = target
		self.local = local

	def print(self, **kwds):
		return "ON " + ("LOCAL " if self.local else "") + "ERROR " + ("RESUME NEXT" if self.target is None else "GOTO " + self.target.print(**kwds))

class OnEventGosubStatement(Element):
	def __init__(self, event, target):
		self.event = event
		self.target = target

	def print(self, **kwds):
		return "ON " + self.event.print(**kwds) + " GOSUB " + self.target.print(**kwds)

class OnGosubStatement(Element):
	def __init__(self, condition, *targets):
		self.condition = condition
		self.targets = list(targets)

	def print(self, **kwds):
		return "ON " + self.condition.print(**kwds) + " GOSUB " + ", ".join(target.print(**kwds) for target in self.targets)

class OnGotoStatement(Element):
	def __init__(self, condition, *targets):
		self.condition = condition
		self.targets = list(targets)

	def print(self, **kwds):
		return "ON " + self.condition.print(**kwds) + " GOTO " + ", ".join(target.print(**kwds) for target in self.targets)

class DoStatement(Element):
	def __init__(self, keyword = None, condition = None):
		assert condition is None or keyword in {'UNTIL', 'WHILE'}
		self.condition = condition
		self.keyword = keyword

	def print(self, **kwds):
		return "DO" + (" " + self.keyword + " " + self.condition.print(**kwds) if self.condition is not None else "")

class LoopStatement(Element):
	def __init__(self, keyword = None, condition = None):
		assert condition is None or keyword in {'UNTIL', 'WHILE'}
		self.condition = condition
		self.keyword = keyword

	def print(self, **kwds):
		return "LOOP" + (" " + self.keyword + " " + self.condition.print(**kwds) if self.condition is not None else "")

class LineIfStatement(Element):
	def __init__(self, condition, then_branch = None, else_branch = None):
		self.condition = condition
		self.then_branch = then_branch if then_branch is not None else EmptyStatement()
		self.else_branch = else_branch

	def print(self, **kwds):
		return "IF " + self.condition.print(**kwds) + " THEN " + self.then_branch.print(**kwds) + (" " + self.else_branch.print(**kwds) if self.else_branch is not None else "")

class BlockIfStatement(Element):
	def __init__(self, condition):
		self.condition = condition

	def print(self, **kwds):
		return "IF " + self.condition.print(**kwds) + " THEN"

class ElseIfStatement(Element):
	def __init__(self, condition):
		self.condition = condition

	def print(self, **kwds):
		return "ELSEIF " + self.condition.print(**kwds) + " THEN"

class ElseStatement(Element):
	def __init__(self, action = None):
		self.action = action if action is not None else EmptyStatement()

	def print(self, **kwds):
		return "ELSE" + (" " + self.action.print(**kwds) if not isinstance(self.action, EmptyStatement) else "")

class ForStatement(Element):
	def __init__(self, var, begin, end, step = None):
		self.var = var
		self.begin = begin
		self.end = end
		self.step = step

	def print(self, **kwds):
		return "FOR " + self.var.print(**kwds) + " = " + self.begin.print(**kwds) + " TO " + self.end.print(**kwds) + (" STEP " + self.step.print(**kwds) if self.step is not None else "")

class NextStatement(Element):
	def __init__(self, *variables):
		self.variables = None if len(variables) == 1 and variables[0] is None else list(variables)

	def print(self, **kwds):
		return "NEXT" + (" " + ", ".join(variable.print(**kwds) for variable in self.variables) if self.variables is not None else "")

class SelectCaseStatement(Element):
	def __init__(self, test):
		self.test = test

	def print(self, **kwds):
		return "SELECT CASE " + self.test.print(**kwds)

class CaseRangeOption(Element):
	def __init__(self, lower_bound, upper_bound):
		self.lower_bound = lower_bound
		self.upper_bound = upper_bound

	def print(self, **kwds):
		return self.lower_bound.print(**kwds) + " TO " + self.upper_bound.print(**kwds)

class CaseIsOption(Element):
	def __init__(self, operator, value):
		self.operator = operator
		self.value = value

	def print(self, **kwds):
		return "IS " + self.operator + " " + self.value.print(**kwds)

class CaseStatement(Element):
	def __init__(self, *options):
		self.options = list(options)

	def print(self, **kwds):
		return "CASE " + ", ".join(option.print(**kwds) for option in self.options)

class CaseElseStatement(Element):
	def print(self, **kwds):
		return "CASE ELSE"

class ArgumentDeclaration(Element):
	def __init__(self, name, as_type, array = False):
		self.name = name
		self.as_type = as_type
		self.array = array

	def print(self, **kwds):
		return self.name.print(**kwds) + ("()" if self.array else "") + (" AS " + self.as_type.get_name() if self.as_type is not None else "")

class DeclareStatement(Element):
	def __init__(self, kind, name, args, cdecl = False, alias = b''):
		assert kind in {'SUB', 'FUNCTION'}
		self.kind = kind
		self.name = name
		self.args = list(args) if args is not None else None
		self.cdecl = cdecl
		self.alias = alias

	def print(self, **kwds):
		return "DECLARE " + self.kind + " " + self.name.print(**kwds) + (" CDECL" if self.cdecl else "") + (" ALIAS \"" + self.alias.decode('cp437') + "\"" if self.alias != b'' else  "") + (" (" + ", ".join(arg.print(**kwds) for arg in self.args) + ")" if self.args is not None else "")

class ProcedureStatement(Element):
	def __init__(self, kind, name, args, static = False, isvbdos = False):
		assert kind in {'SUB', 'FUNCTION'}
		self.kind = kind
		self.name = name
		self.args = list(args) if args is not None else None
		self.static = static
		self.isvbdos = isvbdos

	def print(self, **kwds):
		return ("STATIC " if self.static and self.isvbdos else "") + self.kind + " " + self.name.print(**kwds) + (" (" + ", ".join(arg.print(**kwds) for arg in self.args) + ")" if len(self.args) > 0 else "") + (" STATIC" if self.static and not self.isvbdos else "")

class TypeDeclaration(Element):
	def __init__(self, name):
		self.name = name

	def print(self, **kwds):
		return "TYPE " + self.name.print(**kwds)

class TypeFieldDeclaration(Element):
	def __init__(self, name, as_type, *dimensions, as_column = 0):
		self.name = name
		self.as_type = as_type
		self.dimensions = dimensions
		self.as_column = as_column

	def print(self, column = 0, **kwds):
		if self.dimensions is not None:
			dimensions = []
			for i in range(0, len(self.dimensions), 2):
				if self.dimensions[i] is None:
					dimensions.append(self.dimensions[i + 1].print(**kwds))
				else:
					dimensions.append(self.dimensions[i].print(**kwds) + " TO " + self.dimensions[i + 1].print(**kwds))
			dimensions = "(" + ", ".join(dimensions) + ")"
		else:
			dimensions = ""

		text = self.name.print(**kwds) + dimensions
		if self.as_type is not None:
			text += " " * max(1, self.as_column - (column + len(text))) + "AS " + self.as_type.get_name()
		return text

class EndDeclaration(Element):
	def __init__(self, kind):
		assert kind in {'DEF', 'IF', 'FUNCTION', 'SELECT', 'SUB', 'TYPE'}
		self.kind = kind

	def print(self, **kwds):
		return "END " + self.kind

class ConstDeclaration(Element):
	def __init__(self, *assignments):
		self.assignments = list(assignments)

	def print(self, **kwds):
		return "CONST " + ", ".join(assignment.print(**kwds) for assignment in self.assignments)

class DataDeclaration(Element):
	def __init__(self, text):
		self.text = text

	def print(self, **kwds):
		return "DATA" + self.text.decode('cp437')

class DefFnDeclaration(Element):
	def __init__(self, name, *arguments, isvbdos = False):
		self.name = name
		self.arguments = list(arguments)
		self.definition = None
		self.isvbdos = isvbdos

	def print(self, **kwds):
		return "DEF " + self.name.print(**kwds) + (" (" + ", ".join(argument.print(**kwds) for argument in self.arguments) + ")" if len(self.arguments) > 0 or self.isvbdos else "") + (" = " + self.definition.print(**kwds) if self.definition is not None else "")

class DefTypeDeclaration(Element):
	def __init__(self, as_type, letters):
		self.as_type = as_type
		self.letters = letters

	def print(self, **kwds):
		ranges = []
		for i in range(ord('A'), ord('Z') + 1):
			c = chr(i)
			if c not in self.letters:
				continue
			if len(ranges) > 0 and ranges[-1][1] == chr(i - 1):
				ranges[-1] = (ranges[-1][0], c)
			else:
				ranges.append((c, c))
		return "DEF" + self.as_type.get_short_name() + " " + ", ".join(pair[0] + "-" + pair[1] if pair[0] != pair[1] else pair[0] for pair in ranges)

class VariableDeclaration(Element):
	def __init__(self, name, as_type, as_column = 0, dimensions = None):
		assert as_type is None or type(as_type) in {IntegerType, LongType, SingleType, DoubleType, CurrencyType, StringType, FixedStringType, CustomType}
		self.name = name
		self.as_type = as_type
		self.dimensions = list(dimensions) if dimensions is not None else None
		self.as_column = as_column

	def set_type(self, as_type):
		assert self.as_type is None
		self.as_type = as_type
		return self

	def set_name(self, name, dimensions = None):
		assert self.name is None
		self.name = name
		if dimensions is not None:
			self.dimensions = dimensions

	def print(self, column = 0, **kwds):
		if self.dimensions is not None:
			dimensions = []
			for i in range(0, len(self.dimensions), 2):
				if self.dimensions[i] is None:
					dimensions.append(self.dimensions[i + 1].print(**kwds))
				else:
					dimensions.append(self.dimensions[i].print(**kwds) + " TO " + self.dimensions[i + 1].print(**kwds))
			dimensions = "(" + ", ".join(dimensions) + ")"
		else:
			dimensions = ""
		text = self.name.print(**kwds) + dimensions
		if self.as_type is not None:
			text += " " * max(1, self.as_column - (column + len(text))) + "AS " + self.as_type.get_name()
		return text

class VariableDeclarationStatement(Element):
	def __init__(self):
		self.kind = None
		self.common_block_name = None
		self.mode = None # SHARED or PRESERVE
		self.declarations = []

	def set_kind(self, kind):
		assert self.kind is None or self.kind == kind
		assert kind in {'COMMON', 'DIM', 'REDIM', 'STATIC', 'SHARED'}
		self.kind = kind

	def set_mode(self, mode):
		assert self.mode is None
		assert mode in {'SHARED', 'PRESERVE'}
		self.mode = mode

	def print(self, column = 0, **kwds):
		kind = self.kind if self.kind is not None else '????'
		text = kind + ' ' + (self.mode + ' ' if self.mode is not None else '') + ('/' + self.common_block_name.print(**kwds) + '/ ' if self.common_block_name is not None else '')
		for declaration_index, declaration in enumerate(self.declarations):
			if declaration_index != 0:
				text += ", "
			text += declaration.print(column = column + len(text), **kwds)
		return text

class ErrorInLine(Element):
	def __init__(self, text, rest_of_line = None):
		self.text = text
		self.rest_of_line = rest_of_line

	def print(self, **kwds):
		return self.text.decode('cp437') + (self.rest_of_line.print(**kwds) if self.rest_of_line is not None else "")

class Comment(Element):
	def __init__(self, text, column, metacommand = None):
		self.text = text
		self.column = column
		self.metacommand = metacommand

	def print(self, **kwds):
		return "'" + self.text.decode('cp437') + (self.metacommand.print(**kwds) if self.metacommand is not None else "")

#### BASIC line

class Line(Element):
	def __init__(self, *statements, label = None, indent = 0, comment = None):
		self.statements = list(statements)
		self.columns = [None] * len(statements)
		self.label = label
		self.indent = indent
		self.comment = comment

	def add_statement(self, statement, at_column = None):
		self.statements.append(statement)
		self.columns.append(at_column)

	def print(self, **kwds):
		line = ""
		if self.label is not None:
			if self.label.is_number:
				if type(self.label.name) is int:
					line += str(self.label.name) + ' '
				else:
					line += self.label.name.decode('cp437') + ' '
			else:
				line += self.label.name.decode('cp437') + ': '
		line += ' ' * self.indent
		for statement_index, statement in enumerate(self.statements):
			if statement_index != 0:
				line += ":"
				if self.columns[statement_index] is not None and len(line) < self.columns[statement_index]:
					line += " " * (self.columns[statement_index] - len(line))
				else:
					line += " "
			line += statement.print(column = len(line), **kwds)
			if statement_index != 0:
				line = line.rstrip()
		if self.comment is not None:
			if len(line) < self.comment.column:
				line += ' ' * (self.comment.column - len(line))
			line += self.comment.print(**kwds)
		return line

#### BASIC procedure

class Procedure(Element):
	def __init__(self, name = None, kind = None, static = False):
		self.name = name
		self.lines = []
		self.kind = kind
		self.static = static

	def print(self, file = None, **kwds):
		for line in self.lines:
			print(line.print(**kwds), file = file)

#### BASIC forms and controls

class Attribute:
	def __init__(self, name, _type, value, comment = None):
		assert _type in {'STRING', 'INTEGER', 'CHAR', 'QBCOLOR', 'BOOLEAN', 'UNSIGNED', 'OFFSET', 'SHORTCUT'}
		if _type == 'STRING':
			assert type(value) is bytes
		elif _type == 'SHORTCUT':
			assert type(value) is str
		else:
			assert type(value) is int
		self.name = name
		self.type = _type
		self.value = value
		self.present = True

	def print(self):
		text = f"{self.name:12} = "
		if self.type == 'STRING':
			text += '"' + self.value.decode('cp437').replace('"', '""') + '"'
		elif self.type == 'CHAR':
			text += f'Char({self.value})'
		elif self.type == 'QBCOLOR':
			text += f'QBColor({self.value})'
		else:
			text += str(self.value)
		return text

class Object:
	def __init__(self, name, _type):
		self.name = name
		self.type = _type
		self.attributes = {}
		self.members = []

	def print(self, indent = '', file = None):
		print(indent + "BEGIN " + self.type + " " + self.name, file = file)
		for attribute, value in sorted(self.attributes.items(), key = lambda pair: pair[0]):
			if len(attribute) == 0 or not attribute[0].isalpha():
				continue
			if not value.present:
				continue
			print(indent + "\t" + value.print(), file = file)
		for member in self.members:
			member.print(indent + "\t", file = file)
		print(indent + "END", file = file)

#### Parsing

VBDOS_CONTROL_TYPES = {
	0: ("Form", 0x1F, [
		1,
		(2, "BOOLEAN",
			[None, "MaxButton", None, "AutoRedraw", None, "ControlBox", None, None, "Enabled", None, "MinButton", None, None, None, None, "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		4,
		(1, "CHAR", "*Top"),
		(1, "CHAR", "*Left"),
		(1, "CHAR", "*Height"),
		(1, "CHAR", "*Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "WindowState"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		1,
		(2, "STRING", "Caption"),
		(1, "INTEGER", "BorderStyle"),
		2,
		(1, "INTEGER", "&Height"),
		(1, "INTEGER", "&Width"),
	]),
	1: ("CheckBox", 0x1C, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		(2, "STRING", "Caption"),
		(1, "INTEGER", "Value"),
		1,
	]),
	2: ("ComboBox", 0x27, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, "Sorted", "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		12,
		(2, "STRING", "Text"),
		(1, "INTEGER", "Style"),
	]),
	3: ("CommandButton", 0x1C, [
		1,
		(2, "BOOLEAN",
			[None, None, "Default", None, None, None, None, None, "Enabled", "&Index", None, None, "Cancel", None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		1,
		(1, "INTEGER", "DragMode"),
		(2, "STRING", "Caption"),
		2,
	]),
	4: ("DirListBox", 0x20, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		8,
	]),
	5: ("DriveListBox", 0x20, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		8,
	]),
	6: ("FileListBox", 0x24, [
		1,
		(2, "BOOLEAN",
			["ReadOnly", "Hidden", "System", None, None, "Archive", None, None, "Enabled", "&Index", "Normal", None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		10,
		(2, "STRING", "Pattern"),
	]),
	7: ("Frame", 0x1A, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, None, "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		(2, "STRING", "Caption"),
	]),
	8: ("HScrollBar", 0x20, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, "Attached", "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(2, "INTEGER", "Value"),
		(1, "INTEGER", "DragMode"),
		(2, "INTEGER", "LargeChange"),
		(2, "INTEGER", "SmallChange"),
		(2, "INTEGER", "Max"),
		(2, "INTEGER", "Min"),
	]),
	9: ("Label", 0x1C, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, "AutoSize", None, None, "Enabled", "&Index", None, None, None, None, None, "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		(2, "STRING", "Caption"),
		(1, "INTEGER", "BorderStyle"),
		(1, "INTEGER", "Alignment"),
	]),
	10: ("ListBox", 0x20, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, "Sorted", "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		8,
	]),
	11: ("Menu", 0x1A, [
		1,
		(2, "BOOLEAN",
			["Separator", None, None, None, None, None, "Checked", None, "Enabled", "&Index", None, None, None, None, None, "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		11,
		(2, "STRING", "Caption"),
	]),
	12: ("OptionButton", 0x1C, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		(2, "STRING", "Caption"),
		(1, "BOOLEAN", "Value"),
		1,
	]),
	13: ("PictureBox", 0x1F, [
		1,
		(2, "BOOLEAN",
			[None, None, None, "AutoRedraw", None, None, None, None, "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		2,
		(1, "INTEGER", "BorderStyle"),
		4,
	]),
	14: ("TextBox", 0x22, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, "MultiLine", None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(1, "QBCOLOR", "BackColor"),
		(1, "QBCOLOR", "ForeColor"),
		(1, "INTEGER", "DragMode"),
		2,
		(1, "INTEGER", "BorderStyle"),
		(1, "INTEGER", "ScrollBars"),
		(2, "STRING", "Text"),
		2,
	]),
	15: ("Timer", 0x1C, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, None, "Enabled", "&Index", None, None, None, None, None, None]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		7,
		(2, "UNSIGNED", "Interval"),
		2,
	]),
	16: ("VScrollBar", 0x20, [
		1,
		(2, "BOOLEAN",
			[None, None, None, None, None, None, None, "Attached", "Enabled", "&Index", None, None, None, None, "TabStop", "Visible"]
		),
		2,
		(2, "OFFSET", "~"),
		(2, "STRING", "Tag"),
		(2, "INTEGER", "Index"),
		2,
		(1, "CHAR", "Top"),
		(1, "CHAR", "Left"),
		(1, "CHAR", "Height"),
		(1, "CHAR", "Width"),
		(1, "INTEGER", "MousePointer"),
		(1, "INTEGER", "TabIndex"),
		(2, "INTEGER", "Value"),
		(1, "INTEGER", "DragMode"),
		(2, "INTEGER", "LargeChange"),
		(2, "INTEGER", "SmallChange"),
		(2, "INTEGER", "Max"),
		(2, "INTEGER", "Min"),
	]),
}

class BasicFileVersion:
	# None: count comes from next word in opcode stream
	# -1: no parentheses (only for functions)
	# an optional fourth argument may include the following keyword arguments:
	# - assignment: instructions that look like an assignment
	# - skipped_words: supplementary 16-bit words following the opcode
	# - double_arguments: every missing argument is encoded with 0173, every present one is preceded with 0172
	# - missing_arguments: lists the argument positions that are left empty
	BUILTINS = {
		0x0043: (False, 'CHAIN', 1),
		0x004E: (False, 'END', 0),
		0x0075: (False, 'STOP', 0, {'skipped_words': 1}), # second argument is 0098
		0x0077: (False, 'WAIT', 2),
		0x0078: (False, 'WAIT', 3),
		0x0079: (False, 'WEND', 0, {'skipped_words': 1}),
		0x007A: (False, 'WHILE', 1, {'skipped_words': 1}),
		0x009A: (False, 'BEEP', 0),
		0x009B: (False, 'BLOAD', 1),
		0x009C: (False, 'BLOAD', 2),
		0x009D: (False, 'BSAVE', 3),
		0x009E: (False, 'CHDIR', 1),
		0x00A1: (False, 'CLEAR', None, {'double_arguments': True}),
		0x00A2: (False, 'CLOSE', None),
		0x00A3: (False, 'CLS', 1, {'double_arguments': True}),
		0x00A4: (False, 'COLOR', None, {'double_arguments': True}),
		0x00A7: (False, 'DATE$', -1, {'assignment': True}),
		0x00A8: (False, 'DEF SEG', 0),
		0x00A9: (False, 'DEF SEG', -1, {'assignment': True}),
		0x00AA: (False, 'DRAW', 1),
		0x00AB: (False, 'ENVIRON', 1),
		0x00AD: (False, 'ERROR', 1),
		0x00AE: (False, 'FILES', 0),
		0x00AF: (False, 'FILES', 1),
		0x00B0: (False, 'GET', 1),
		0x00B1: (False, 'GET', 2),
		0x00B2: (False, 'GET', 2, {'missing_arguments': {1}, 'skipped_words': 1}),
		0x00B3: (False, 'GET', 3, {'skipped_words': 1}),
		0x00B7: (False, 'IOCTL', 2),
		0x00B9: (False, 'KEY', 2),
		0x00BA: (False, 'KILL', 1),
		0x00C1: (False, 'LOCATE', None, {'double_arguments': True}),
		0x00C5: (False, 'MID$', 2, {'assignment': True}),
		0x00C6: (False, 'MID$', 3, {'assignment': True}),
		0x00C7: (False, 'MKDIR', 1),
		0x00CB: (False, 'OPEN', 3),
		0x00CC: (False, 'OPEN', 4),
		0x00CD: (False, 'OPTION BASE 0', 0),
		0x00CE: (False, 'OPTION BASE 1', 0),
		0x00CF: (False, 'OUT', 2),
		0x00D2: (False, 'PALETTE', 0),
		0x00D3: (False, 'PALETTE', 2),
		0x00D4: (False, 'PALETTE USING', 1),
		0x00D5: (False, 'PCOPY', 2),
		0x00D6: (False, 'PLAY', 1),
		0x00D7: (False, 'POKE', 2),
		0x00DC: (False, 'PUT', 1),
		0x00DD: (False, 'PUT', 2),
		0x00DE: (False, 'PUT', 2, {'missing_arguments': {1}, 'skipped_words': 1}),
		0x00DF: (False, 'PUT', 3, {'skipped_words': 1}),
		0x00E0: (False, 'RANDOMIZE', 0),
		0x00E1: (False, 'RANDOMIZE', 1),
		0x00E4: (False, 'RESET', 0),
		0x00E5: (False, 'RMDIR', 1),
		0x00E7: (False, 'SCREEN', None, {'double_arguments': True}),
		0x00E8: (False, 'SEEK', 2),
		0x00E9: (False, 'SHELL', 0),
		0x00EA: (False, 'SHELL', 1),
		0x00EB: (False, 'SLEEP', 0),
		0x00EC: (False, 'SOUND', 2),
		0x00ED: (False, 'SWAP', 2, {'skipped_words': 1}),
		0x00EE: (False, 'SYSTEM', 0),
		0x00EF: (False, 'TIME$', -1, {'assignment': True}),
		0x00F0: (False, 'TROFF', 0),
		0x00F1: (False, 'TRON', 0),
		0x00F4: (False, 'VIEW', 0),
		0x00F9: (False, 'WIDTH LPRINT', 1),
		0x00FA: (False, 'WIDTH', 2), # first argument is file name
		0x00FC: (False, 'WINDOW', 0),
		0x0105: (True, 'ABS', 1),
		0x0106: (True, 'ASC', 1),
		0x0107: (True, 'ATN', 1),
		0x0109: (True, 'CHR$', 1),
		0x010A: (True, 'COMMAND$', -1),
		0x010B: (True, 'COS', 1),
		0x010C: (True, 'CSRLIN', -1),
		0x010D: (True, 'CVD', 1),
		0x010E: (True, 'CVDMBF', 1),
		0x010F: (True, 'CVI', 1),
		0x0110: (True, 'CVL', 1),
		0x0111: (True, 'CVS', 1),
		0x0112: (True, 'CVSMBF', 1),
		0x0113: (True, 'DATE$', -1),
		0x0114: (True, 'ENVIRON$', 1),
		0x0115: (True, 'EOF', 1),
		0x0116: (True, 'ERDEV', -1),
		0x0117: (True, 'ERDEV$', -1),
		0x0118: (True, 'ERL', -1),
		0x0119: (True, 'ERR', -1),
		0x011A: (True, 'EXP', 1),
		0x011B: (True, 'FILEATTR', 2),
		0x011C: (True, 'FIX', 1),
		0x011D: (True, 'FRE', 1),
		0x011E: (True, 'FREEFILE', -1),
		0x011F: (True, 'HEX$', 1),
		0x0120: (True, 'INKEY$', -1),
		0x0121: (True, 'INP', 1),
		0x0122: (True, 'INPUT$', 1),
		0x0123: (True, 'INPUT$', 2),
		0x0124: (True, 'INSTR', 2),
		0x0125: (True, 'INSTR', 3),
		0x0126: (True, 'INT', 1),
		0x0127: (True, 'IOCTL$', 1),
		0x0128: (True, 'LBOUND', 1),
		0x0129: (True, 'LBOUND', 2),
		0x012A: (True, 'LCASE$', 1),
		0x012B: (True, 'LTRIM$', 1),
		0x012C: (True, 'LEFT$', 2),
		0x012D: (True, 'LEN', 1, {'skipped_words': 1}),
		0x012E: (True, 'LOC', 1),
		0x012F: (True, 'LOF', 1),
		0x0130: (True, 'LOG', 1),
		0x0131: (True, 'LPOS', 1),
		0x0132: (True, 'MID$', 2),
		0x0133: (True, 'MID$', 3),
		0x0134: (True, 'MKD$', 1),
		0x0135: (True, 'MKDMBF$', 1),
		0x0136: (True, 'MKI$', 1),
		0x0137: (True, 'MKL$', 1),
		0x0138: (True, 'MKS$', 1),
		0x0139: (True, 'MKSMBF$', 1),
		0x013A: (True, 'OCT$', 1),
		0x013B: (True, 'PEEK', 1),
		0x013C: (True, 'PEN', 1),
		0x013D: (True, 'PLAY', 1),
		0x013E: (True, 'PMAP', 2),
		0x013F: (True, 'POINT', 1),
		0x0140: (True, 'POINT', 2),
		0x0141: (True, 'POS', 1),
		0x0142: (True, 'RIGHT$', 2),
		0x0143: (True, 'RND', -1),
		0x0144: (True, 'RND', 1),
		0x0145: (True, 'RTRIM$', 1),
		0x0146: (True, 'SADD', 1),
		0x0147: (True, 'SCREEN', 2),
		0x0148: (True, 'SCREEN', 3),
		0x0149: (True, 'SEEK', 1),
		0x014A: (True, 'SETMEM', 1),
		0x014B: (True, 'SGN', 1),
		0x014C: (True, 'SHELL', 1),
		0x014D: (True, 'SIN', 1),
		0x014E: (True, 'SPACE$', 1),
		0x014F: (True, 'SQR', 1),
		0x0150: (True, 'STICK', 1),
		0x0151: (True, 'STR$', 1),
		0x0152: (True, 'STRIG', 1),
		0x0153: (True, 'STRING$', 2),
		0x0154: (True, 'TAN', 1),
		0x0155: (True, 'TIME$', -1),
		0x0156: (True, 'TIMER', -1),
		0x0157: (True, 'UBOUND', 1),
		0x0158: (True, 'UBOUND', 2),
		0x0159: (True, 'UCASE$', 1),
		0x015A: (True, 'VAL', 1),
		0x015B: (True, 'VARPTR', 1),
		0x015C: (True, 'VARPTR$', 1, {'skipped_words': 1}),
		0x015D: (True, 'VARSEG', 1),
	# QB45+
		0x017B: (False, 'SLEEP', 1),
	# QB70+
		0x017F: (False, 'CHDRIVE', 1),
		0x0180: (False, 'ERR', -1, {'assignment': True}),
		0x0181: (True, 'CURDIR$', -1),
		0x0182: (True, 'CURDIR$', 1),
		0x0183: (True, 'DIR$', -1),
		0x0184: (True, 'DIR$', 1),
		0x0186: (True, 'BOF', 1),
		0x0187: (True, 'CVC', 1),
		0x0188: (True, 'GETINDEX$', 1),
		0x0189: (True, 'MKC$', 1),
		0x018A: (True, 'SAVEPOINT', -1),
		0x018B: (True, 'SSEG', 1),
		0x018C: (True, 'SSEGADD', 1),
		0x018D: (True, 'STACK', -1),
		0x018E: (False, 'BEGINTRANS', 0),
		0x018F: (False, 'CHECKPOINT', 0),
		0x0190: (False, 'COMMITTRANS', 0),
		0x0191: (False, 'CREATEINDEX', None),
		0x0192: (False, 'DELETE', 1),
		0x0193: (False, 'DELETEINDEX', 2),
		0x0194: (False, 'DELETETABLE', 2),
		0x0195: (False, 'END', 1),
		0x0197: (False, 'INSERT', 2),
		0x019B: (False, 'RETRIEVE', 2),
		0x019C: (False, 'ROLLBACK', 0),
		0x019D: (False, 'ROLLBACK', 1),
		0x019E: (False, 'ROLLBACK ALL', 0),
		0x01A0: (False, 'SETINDEX', 1),
		0x01A1: (False, 'SETINDEX', 2),
		0x01A2: (False, 'STACK', 0),
		0x01A3: (False, 'STACK', 1),
		0x01A4: (False, 'STOP', 1, {'skipped_words': 1}), # second argument is 0098
		0x01A5: (False, 'SYSTEM', 1),
		0x01A6: (False, 'UPDATE', 2),
		0x01A7: (True, 'TEXTCOMP', 2),
	# VBDOS
		0x01AB: (False, 'LOAD', 1),
		0x01AC: (False, 'UNLOAD', 1),
		0x01AD: (True, 'DOEVENTS', 0),
		0x01AE: (True, 'QBCOLOR', 1),
		0x01AF: (True, 'RGB', 3),
		0x01B0: (True, 'ERROR$', -1),
		0x01B1: (True, 'ERROR$', 1),
		0x01B2: (True, 'FORMAT$', 1),
		0x01B3: (True, 'FORMAT$', 2),
		0x01B4: (True, 'DATESERIAL', 3),
		0x01B5: (True, 'DATEVALUE', 1),
		0x01B6: (True, 'DAY', 1),
		0x01B7: (True, 'MONTH', 1),
		0x01B8: (True, 'WEEKDAY', 1),
		0x01B9: (True, 'YEAR', 1),
		0x01BA: (True, 'NOW', -1),
		0x01BB: (True, 'TIMESERIAL', 3),
		0x01BC: (True, 'TIMEVALUE', 1),
		0x01BD: (True, 'HOUR', 1),
		0x01BE: (True, 'MINUTE', 1),
		0x01BF: (True, 'SECOND', 1),
		0x01C0: (False, 'OPTION EXPLICIT', 0),
		0x01C3: (True, 'INPUTBOX$', 3),
		0x01C4: (True, 'INPUTBOX$', 5),
		0x01C5: (False, 'MSGBOX', 3),
		0x01C6: (True, 'MSGBOX', 3),
	}

	def get_version_stamp(self):
		raise Exception

	def get_header_size(self):
		raise Exception

	def get_default_procedure_offset(self):
		return 0x159

	def get_maximum_opcode(self):
		raise Exception

	def get_maximum_builtin_type(self):
		raise Exception

	def get_type(self, cxt, file, index):
		if index == 0:
			return AnyType()
		elif index <= self.get_maximum_builtin_type():
			return self.get_builtin_type(index)
		elif (index & 0x8000) != 0:
			return FixedStringType(index & 0x7FFF)
		else:
			return CustomType(cxt.qbfile.readvar(file, index))

	def parse_header(self, qbfile, file):
		file.seek(qbfile.header_size - 2, os.SEEK_SET)
		qbfile.procedures_offset = read16(file)

	def parse_opcodes(self, cxt, file):
		length = read16(file)
		start = file.tell()
		while file.tell() < length + start:
			opcode = read16(file)
			self.parse_opcode(cxt, file, opcode)

	def expand_comment(self, text):
		result = b""
		i = 0
		while i < len(text):
			if i + 2 < len(text) and text[i] == 0x0D:
				result += text[i + 2:i + 3] * text[i + 1]
				i += 3
			else:
				result += text[i:i + 1]
				i += 1
		return result

	def parse_opcode(self, cxt, file, opcode, parameter = None, actual_opcode = None):
		if parameter is None:
			parameter = opcode >> 10
		opcode &= 0x3FF
		if actual_opcode is None:
			actual_opcode = opcode
		if opcode > self.get_maximum_opcode():
			raise Exception(f"Invalid opcode {actual_opcode:04X}")
		if opcode == 0x0000:
			cxt.clear()
			cxt.begin_line(indent = parameter)
		elif opcode == 0x0004:
			cxt.clear()
			read16(file)
			name = cxt.readvar(file)
			cxt.begin_line(label = name)
		elif opcode == 0x0005:
			cxt.clear()
			read16(file)
			name = cxt.readvar(file)
			indent = read16(file)
			cxt.begin_line(label = name, indent = indent)
		elif opcode == 0x0006:
			cxt.new_statement()
		elif opcode == 0x0007:
			cxt.new_statement(read16(file))
		elif opcode == 0x0009:
			read16(file) # 0x0008
			pass
		elif opcode == 0x000A:
			text = reads(file)
			cxt.put_statement(ErrorInLine(text[2:]))
		elif opcode == 0x000B:
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			cxt.push(name)
		elif opcode == 0x000C:
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			source = cxt.pop()
			cxt.put_assignment_statement(AssignmentStatement(name, source))
		elif opcode == 0x000D:
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			cxt.put_declaration().set_name(name)
		elif opcode == 0x000E:
			argcount = read16(file)
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			if (argcount & 0x8000) == 0:
				dims = cxt.pop(argcount)
				cxt.push(ArrayElement(name, *dims))
			else:
				cxt.push(ArrayElement(name, implicit_dims = True))
		elif opcode == 0x000F:
			argcount = read16(file)
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			value = cxt.pop()
			dims = cxt.pop(argcount)
			cxt.put_statement(AssignmentStatement(ArrayElement(name, *dims), value))
		elif opcode == 0x0010:
			if self.get_version_stamp() == BasicFileVersionQB40.VERSION_STAMP \
			and (cxt.peek_statement(VariableDeclarationStatement) is None \
			or cxt.peek_statement(VariableDeclarationStatement).kind in {None, 'DIM', 'REDIM'}):
				# QB40 treats this case like 0x000E
				argcount = read16(file)
				name = cxt.readvar(file)
				if parameter != 0:
					name.suffix = self.get_builtin_type(parameter)
				if (argcount & 0x8000) == 0:
					dims = cxt.pop(argcount)
					cxt.push(ArrayElement(name, *dims))
				else:
					cxt.push(ArrayElement(name, implicit_dims = True))
			else:
				argcount = read16(file)
				name = cxt.readvar(file)
				if parameter != 0:
					name.suffix = self.get_builtin_type(parameter)
				args = cxt.pop(argcount)
				cxt.put_declaration().set_name(name, args)
		elif opcode == 0x0011:
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			arg = cxt.pop()
			cxt.push(FieldSelection(arg, name))
		elif opcode == 0x0012:
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			var = cxt.pop()
			source = cxt.pop()
			cxt.put_statement(AssignmentStatement(FieldSelection(var, name), source))
		elif opcode == 0x0013:
			argcount = read16(file)
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			arg = cxt.pop()
			dims = cxt.pop(argcount)
			field = ArrayElement(name, *dims)
			cxt.push(FieldSelection(arg, field))
		elif opcode == 0x0014:
			argcount = read16(file)
			name = cxt.readvar(file)
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			var = cxt.pop()
			dims = cxt.pop(argcount)
			source = cxt.pop()
			field = ArrayElement(name, *dims)
			cxt.put_statement(AssignmentStatement(FieldSelection(var, field), source))
		elif opcode == 0x0015:
			type_offset = read16(file)
			column = read16(file)
			cxt.put_declaration().set_type(self.get_type(cxt, file, type_offset)).as_column = column
		elif opcode == 0x0016:
			typeidx = read16(file)
			column = read16(file)
			cxt.put_declaration().set_type(self.get_builtin_type(typeidx)).as_column = column
		elif opcode == 0x0017:
			pass # line contains variables with '.' in it
		elif opcode == 0x0018:
			# default array base
			cxt.push(None)
		elif opcode == 0x0019:
			name = cxt.readvar(file)
			mode = read16(file) # 0015/0016/017C
			if mode == 0x017C:
				read16(file)
				size = read16(file)
				as_type = FixedStringType(size)
			else:
				as_type = self.get_type(cxt, file, read16(file))
			column = read16(file)
			cxt.put_statement(TypeFieldDeclaration(name, as_type, as_column = column))
		elif opcode == 0x001A:
			cxt.put_statement_kind(VariableDeclarationStatement).mode = 'SHARED'
		elif opcode == 0x001B:
			read16(file)
			data = read32(file)
			as_type = self.get_builtin_type(data & 0x3F)
			letters = set()
			for i in range(ord('A'), ord('Z') + 1):
				if (data & (1 << (31 - (i - ord('A'))))) != 0:
					letters.add(chr(i))
			cxt.put_statement(DefTypeDeclaration(as_type, letters))
		elif opcode == 0x001C or opcode == 0x01A8: # QB71+
			array_element = cxt.pop()
			cxt.put_declaration().set_name(array_element.name, array_element.args)
			cxt.put_statement_kind(VariableDeclarationStatement).set_kind('REDIM')
			if opcode == 0x01A8:
				cxt.put_statement_kind(VariableDeclarationStatement).mode = 'PRESERVE'
		elif opcode == 0x001D:
			read16(file)
			cxt.put_statement(EndDeclaration('TYPE'))
		elif opcode == 0x001E:
			read16(file)
			cxt.put_statement_kind(VariableDeclarationStatement).set_kind('SHARED')
		elif opcode == 0x001F:
			read16(file)
			cxt.put_statement_kind(VariableDeclarationStatement).set_kind('STATIC')
		elif opcode == 0x0020:
			read16(file)
			name = cxt.readvar(file)
			cxt.put_statement(TypeDeclaration(name))
		elif opcode == 0x0021:
			read16(file)
			cxt.put_metacommand(MetaCommand("$STATIC"))
		elif opcode == 0x0022:
			read16(file)
			cxt.put_metacommand(MetaCommand("$DYNAMIC"))
		elif opcode == 0x0023:
			cxt.put_statement(ConstDeclaration())
		elif opcode == 0x0025:
			arg = cxt.pop()
			cxt.push(ByValue(arg))
		elif opcode == 0x0026:
			body = cxt.pop()
			cxt.end_deffn(body)
			read16(file)
			read16(file)
		elif opcode == 0x0027:
			arg = cxt.pop()
			cxt.push(EventSpecification("COM", arg))
		elif opcode == 0x0028:
			arg = cxt.pop()
			target = cxt.readvar(file)
			cxt.put_statement(OnEventGosubStatement(arg, target))
		elif opcode == 0x0029:
			arg = cxt.pop()
			cxt.push(EventSpecification("KEY", arg))
		elif opcode == 0x002A:
			arg = cxt.pop()
			cxt.put_statement(EventStatement(arg, "OFF"))
		elif opcode == 0x002B:
			arg = cxt.pop()
			cxt.put_statement(EventStatement(arg, "ON"))
		elif opcode == 0x002C:
			arg = cxt.pop()
			cxt.put_statement(EventStatement(arg, "STOP"))
		elif opcode == 0x002D:
			cxt.push(EventSpecification("PEN"))
		elif opcode == 0x002E:
			cxt.push(EventSpecification("PLAY"))
		elif opcode == 0x002F:
			arg = cxt.pop()
			cxt.push(EventSpecification("PLAY", arg))
		elif opcode == 0x0030:
			arg = cxt.pop()
			cxt.push(EventSpecification("SIGNAL", arg))
		elif opcode == 0x0031:
			arg = cxt.pop()
			cxt.push(EventSpecification("STRIG", arg))
		elif opcode == 0x0032:
			cxt.push(EventSpecification("TIMER"))
		elif opcode == 0x0033:
			arg = cxt.pop()
			cxt.push(EventSpecification("TIMER", arg))
		elif opcode == 0x0036:
			arg = cxt.pop()
			cxt.push(AsSegmented(arg))
		elif opcode == 0x0037:
			argcount = read16(file)
			name = cxt.readvar(file)
			args = cxt.pop(argcount)
			cxt.put_statement(CallStatement(name, *args, explicit = True))
		elif opcode == 0x0038:
			argcount = read16(file)
			name = cxt.readvar(file)
			args = cxt.pop(argcount)
			cxt.put_statement(CallStatement(name, *args, explicit = False))
		elif opcode == 0x0039:
			argcount = read16(file)
			name = cxt.readvar(file)
			args = cxt.pop(argcount)
			cxt.put_statement(CallsStatement(name, *args))
		elif opcode == 0x003A:
			cxt.put_statement(CaseElseStatement())
		elif opcode == 0x003B:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(arg)
		elif opcode == 0x003C:
			args = cxt.pop(2)
			cxt.put_statement_kind(CaseStatement).options.append(CaseRangeOption(*args))
		elif opcode == 0x003D:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('=', arg))
		elif opcode == 0x003E:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('<', arg))
		elif opcode == 0x003F:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('>', arg))
		elif opcode == 0x0040:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('<=', arg))
		elif opcode == 0x0041:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('>=', arg))
		elif opcode == 0x0042:
			arg = cxt.pop()
			cxt.put_statement_kind(CaseStatement).options.append(CaseIsOption('<>', arg))
		elif opcode == 0x0044:
			read16(file)
			name = cxt.readvar(file)
			flags = read16(file)
			if (flags & 0x0300) not in {0x0100, 0x0200}:
				raise Exception(f"Invalid flags {flags:04X}")
			elif (flags & 0x0100) != 0:
				kind = 'SUB'
			elif (flags & 0x0200) != 0:
				kind = 'FUNCTION'
			if (flags & 0x0080) != 0:
				name.suffix = self.get_builtin_type(flags & 7)
			argcount = read16(file)
			alias_length = (flags >> 10) & 0x1F
			if argcount == 0xFFFF:
				args = None
			else:
				args = []
				for i in range(argcount):
					arg_name = cxt.readvar(file)
					mode = read16(file)
					arg_type = self.get_type(cxt, file, read16(file))
					if self.get_version_stamp() >= BasicFileVersionQB71.VERSION_STAMP:
						read16(file)
					args.append(ArgumentDeclaration(arg_name, arg_type, array = (mode & 0x0400) != 0))
			if alias_length != 0:
				alias = file.read(alias_length)
				if alias_length & 1:
					file.read(1)
			else:
				alias = b''
			cxt.put_statement(DeclareStatement(kind, name, args, cdecl = (flags & 0x8000) != 0, alias = alias))
		elif opcode == 0x0045:
			read16(file)
			read16(file)
			name = cxt.readvar(file)
			flags = read16(file)
			if (flags & 0x0080) != 0:
				name.suffix = self.get_builtin_type(flags & 0xF)
			argcount = read16(file)
			args = []
			for i in range(argcount):
				arg_name = cxt.readvar(file)
				mode = read16(file)
				as_type = read16(file)
				if self.get_version_stamp() >= BasicFileVersionQB71.VERSION_STAMP:
					read16(file)
				if (mode & 0x2000) != 0:
					args.append(ArgumentDeclaration(arg_name, self.get_builtin_type(as_type)))
				else:
					if (mode & 0x0200) != 0:
						arg_name.suffix = self.get_builtin_type(as_type)
					args.append(ArgumentDeclaration(arg_name, None))
			cxt.begin_deffn(DefFnDeclaration(name, *args, isvbdos = self.get_version_stamp() == BasicFileVersionVBDOS.VERSION_STAMP))
		elif opcode == 0x0046:
			cxt.put_statement(DoStatement())
		elif opcode == 0x0047:
			arg = cxt.pop()
			cxt.put_statement(DoStatement('UNTIL', arg))
			read16(file)
		elif opcode == 0x0048:
			arg = cxt.pop()
			cxt.put_statement(DoStatement('WHILE', arg))
			read16(file)
		elif opcode == 0x0049:
			cxt.put_statement(ElseStatement())
			read16(file)
		elif opcode == 0x004C:
			arg = cxt.pop()
			read16(file)
			target = cxt.readvar(file)
			cxt.put_statement(ElseStatement(GotoStatement(target, implicit = True)))
		elif opcode == 0x004D:
			arg = cxt.pop()
			cxt.put_statement(ElseIfStatement(arg))
			read16(file)
		elif opcode == 0x004F:
			cxt.put_statement(EndDeclaration('DEF'))
			read16(file)
			read16(file)
		elif opcode == 0x0050:
			cxt.put_statement(EndDeclaration('IF'))
		elif opcode == 0x0051:
			cxt.put_statement(EndDeclaration(cxt.qbfile.procedures[-1].kind))
		elif opcode == 0x0052:
			cxt.put_statement(EndDeclaration('SELECT'))
		elif opcode == 0x0053:
			cxt.put_statement(ExitStatement('DO'))
			read16(file)
		elif opcode == 0x0054:
			cxt.put_statement(ExitStatement('FOR'))
			read16(file)
		elif opcode == 0x0055:
			cxt.put_statement(ExitStatement(cxt.get_exit_kind()))
			read16(file)
		elif opcode == 0x0056:
			args = cxt.pop(3)
			cxt.put_statement(ForStatement(*args))
			read16(file)
			read16(file)
		elif opcode == 0x0057:
			args = cxt.pop(4)
			cxt.put_statement(ForStatement(*args))
			read16(file)
			read16(file)
		elif opcode == 0x0058:
			read16(file)
			name = cxt.readvar(file)
			flags = read16(file)
			if (flags & 0x0080) != 0:
				name.suffix = self.get_builtin_type(flags & 7)
			argcount = read16(file)
			args = []
			for i in range(argcount):
				arg_name = cxt.readvar(file)
				mode = read16(file)
				if (mode & 0x2000) != 0:
					arg_type = self.get_type(cxt, file, read16(file))
				else:
					read16(file)
					arg_type = None
				if self.get_version_stamp() >= BasicFileVersionQB71.VERSION_STAMP:
					read16(file)
				args.append(ArgumentDeclaration(arg_name, arg_type, array = (mode & 0x0400) != 0))
			cxt.qbfile.procedures[-1].kind = 'FUNCTION'
			cxt.put_statement(ProcedureStatement('FUNCTION', name, args, static = cxt.qbfile.procedures[-1].static, isvbdos = self.get_version_stamp() >= BasicFileVersionVBDOS.VERSION_STAMP))
		elif opcode == 0x0059:
			target = cxt.readvar(file)
			cxt.put_statement(GosubStatement(target))
		elif opcode == 0x005B:
			target = cxt.readvar(file)
			cxt.put_statement(GotoStatement(target))
		elif opcode == 0x005D:
			arg = cxt.pop()
			cxt.put_statement(LineIfStatement(arg))
			read16(file)
		elif opcode == 0x005E:
			arg = cxt.pop()
			target = cxt.readvar(file)
			cxt.put_statement(LineIfStatement(arg, GotoStatement(target, implicit = True)))
		elif opcode == 0x0061:
			arg = cxt.pop()
			cxt.put_statement(BlockIfStatement(arg))
			read16(file)
		elif opcode == 0x0062:
			cxt.put_statement(LoopStatement())
			read16(file)
		elif opcode == 0x0063:
			arg = cxt.pop()
			cxt.put_statement(LoopStatement('UNTIL', arg))
			read16(file)
		elif opcode == 0x0064:
			arg = cxt.pop()
			cxt.put_statement(LoopStatement('WHILE', arg))
			read16(file)
		elif opcode == 0x0065:
			cxt.put_statement(NextStatement(None))
			read16(file)
			read16(file)
		elif opcode == 0x0066:
			arg = cxt.pop()
			cxt.put_statement_kind(NextStatement).variables.append(arg)
			read16(file)
			read16(file)
		elif opcode == 0x0067 or opcode == 0x0199: # QB70+
			if self.get_version_stamp() >= BasicFileVersionQB70.VERSION_STAMP:
				target_offset = read16(file)
				if target_offset == 0xFFFF:
					target = DecimalInteger(0) # instead of identifier
				elif target_offset == 0xFFFE:
					target = None # for RESUME NEXT
				else:
					target = cxt.qbfile.readvar(file, target_offset)
			else:
				target = cxt.readvar(file)
			cxt.put_statement(OnErrorGotoStatement(target, local = opcode == 0x0199))
		elif opcode == 0x0068:
			arg = cxt.pop()
			target_count = read16(file)
			targets = []
			for i in range(0, target_count, 2):
				targets.append(cxt.readvar(file))
			cxt.put_statement(OnGosubStatement(arg, *targets))
		elif opcode == 0x0069:
			arg = cxt.pop()
			target_count = read16(file)
			targets = []
			for i in range(0, target_count, 2):
				targets.append(cxt.readvar(file))
			cxt.put_statement(OnGotoStatement(arg, *targets))
		elif opcode == 0x006A:
			cxt.put_statement(RestoreStatement())
		elif opcode == 0x006B:
			arg = cxt.readvar(file)
			cxt.put_statement(RestoreStatement(arg))
		elif opcode == 0x006C:
			cxt.put_statement(ResumeStatement())
		elif opcode == 0x006D:
			label_offset = read16(file)
			if label_offset != 0xFFFF:
				label = cxt.qbfile.readvar(file, label_offset)
			else:
				label = DecimalInteger(0)
			cxt.put_statement(ResumeStatement(label))
		elif opcode == 0x006E:
			cxt.put_statement(ResumeStatement(None))
		elif opcode == 0x006F:
			cxt.put_statement(ReturnStatement())
		elif opcode == 0x0070:
			target = cxt.readvar(file)
			cxt.put_statement(ReturnStatement(target))
		elif opcode == 0x0071:
			arg = cxt.pop()
			cxt.put_statement(RunStatement(arg))
		elif opcode == 0x0072:
			target = cxt.readvar(file)
			cxt.put_statement(RunStatement(target))
		elif opcode == 0x0073:
			cxt.put_statement(RunStatement())
		elif opcode == 0x0074:
			arg = cxt.pop()
			cxt.put_statement(SelectCaseStatement(arg))
			read16(file)
		elif opcode == 0x0076:
			read16(file)
			name = cxt.readvar(file)
			flags = read16(file)
			argcount = read16(file)
			args = []
			for i in range(argcount):
				arg_name = cxt.readvar(file)
				mode = read16(file)
				if (mode & 0x2000) != 0:
					arg_type = self.get_type(cxt, file, read16(file))
				else:
					read16(file)
					arg_type = None
				if self.get_version_stamp() >= BasicFileVersionQB71.VERSION_STAMP:
					read16(file)
				args.append(ArgumentDeclaration(arg_name, arg_type, array = (mode & 0x0400) != 0))
			cxt.qbfile.procedures[-1].kind = 'SUB'
			cxt.put_statement(ProcedureStatement('SUB', name, args, static = cxt.qbfile.procedures[-1].static, isvbdos = self.get_version_stamp() >= BasicFileVersionVBDOS.VERSION_STAMP))
		elif opcode == 0x007D:
			cxt.put_statement_kind(PrintStatement).add_filenumber(cxt.pop())
		elif opcode == 0x007E:
			arg = cxt.pop()
			cxt.set_argument('aspect', arg)
		elif opcode == 0x007F:
			arg = cxt.pop()
			cxt.set_argument('end', arg)
		elif opcode == 0x0080:
			arg = cxt.pop()
			cxt.set_argument('start', arg)
		elif opcode == 0x0081 or opcode == 0x0082:
			args = cxt.pop(2)
			cxt.set_argument('from', CoordinatePair(*args, step = opcode == 0x0082))
		elif opcode == 0x0083 or opcode == 0x0084:
			args = cxt.pop(2)
			cxt.set_argument('to', CoordinatePair(*args, step = opcode == 0x0084))
		elif opcode == 0x0085:
			arg = cxt.pop()
			cxt.put_statement(FieldStatement(arg))
		elif opcode == 0x0086:
			args = cxt.pop(2)
			cxt.get_statement(FieldStatement).associations.append(FieldAssociation(*args))
		elif opcode == 0x0087:
			arg = cxt.pop() # file number
			cxt.put_statement(InputStatement(arg))
		elif opcode == 0x0088:
			cxt.get_statement(InputStatement).kind = 'INPUT'
		elif opcode == 0x0089:
			argcount = read16(file)
			flags = read16(file)
			if (flags & 0x0004) != 0:
				spec = cxt.pop()
			else:
				spec = None
			if argcount > 2:
				read16(file)
			cxt.put_statement(InputStatement(specification = spec, starts_with_semicolon = (flags & 0x0002) != 0, follows_with_comma = (flags & 0x0001) != 0))
		elif opcode == 0x008A:
			arg = cxt.pop()
			cxt.push(FileNumber(arg))
		elif opcode == 0x008F:
			cxt.put_statement_kind(PrintStatement).add_item(PrintControl('SPC', cxt.pop()))
		elif opcode == 0x0090:
			cxt.put_statement_kind(PrintStatement).add_item(PrintControl('TAB', cxt.pop()))
		elif opcode == 0x0091:
			cxt.put_statement_kind(PrintStatement).add_item(PrintItem(separator = ','))
		elif opcode == 0x0092:
			cxt.put_statement_kind(PrintStatement).add_item(PrintItem(separator = ';'))
		elif opcode == 0x0093:
			cxt.put_statement_kind(PrintStatement) # terminate print statement with no expression
		elif opcode == 0x0094:
			cxt.put_statement_kind(PrintStatement).add_item(PrintItem(cxt.pop(), separator = ','))
		elif opcode == 0x0095:
			cxt.put_statement_kind(PrintStatement).add_item(PrintItem(cxt.pop(), separator = ';'))
		elif opcode == 0x0096:
			cxt.put_statement_kind(PrintStatement).add_item(cxt.pop())
		elif opcode == 0x0097:
			assert cxt.qbfile.procedures[-1].lines[-1].comment is None
			text = reads(file)
			column = text[0] | (text[1] << 8)
			text = self.expand_comment(text[2:])
			cxt.qbfile.procedures[-1].lines[-1].comment = Comment(text, column)
		elif opcode == 0x0099:
			text = reads(file)
			cxt.put_metacommand(MetaCommand("$INCLUDE", IncludeText(text[:-1])))
		elif opcode == 0x009F or opcode == 0x00A0:
			center = cxt.get_argument('from')
			if opcode == 0x00A0:
				color = cxt.pop()
			else:
				color = None
			radius = cxt.pop()
			start = cxt.get_argument('start')
			end = cxt.get_argument('end')
			aspect = cxt.get_argument('aspect')
			cxt.put_statement(CircleStatement(center, radius, color, start, end, aspect))
		elif opcode == 0x00A5:
			read16(file)
			name_offset = read16(file)
			if name_offset != 0xFFFF:
				name = cxt.qbfile.readvar(file, name_offset)
			else:
				name = None
			cxt.put_statement_kind(VariableDeclarationStatement).set_kind('COMMON')
			cxt.put_statement_kind(VariableDeclarationStatement).common_block_name = name
		elif opcode == 0x00A6:
			text = reads(file)
			cxt.put_statement(DataDeclaration(text[2:-1]))
		elif opcode == 0x00AC:
			if self.get_version_stamp() < BasicFileVersionQB70.VERSION_STAMP:
				argcount = read16(file)
				args = cxt.pop(argcount)
				cxt.put_statement(EraseStatement(*args))
			else:
				arg = cxt.pop()
				cxt.add_statement(EraseStatement).arguments.append(arg)
		elif opcode == 0x00B4:
			_from = cxt.get_argument('from')
			to = cxt.get_argument('to')
			arrayspec = cxt.pop()
			cxt.put_statement(GetStatement(_from, to, arrayspec))
		elif opcode == 0x00B5:
			method = read16(file)
			_from = cxt.get_argument('from')
			arrayspec = cxt.pop()
			cxt.put_statement(PutStatement(_from, arrayspec, ['OR', 'AND', 'PRESET', 'PSET', 'XOR'][method] if method != 0xFFFF else None))
		elif opcode == 0x00B6:
			arg = cxt.pop()
			cxt.get_statement(InputStatement).arguments.append(arg)
		elif opcode == 0x00B8:
			mode = read16(file)
			cxt.put_statement(KeyStatement(['OFF', 'ON', 'LIST'][mode]))
		elif opcode == 0x00BB or opcode == 0x00BC or opcode == 0x00BD or opcode == 0x00BE:
			mode = read16(file)
			_from = cxt.get_argument('from')
			to = cxt.get_argument('to')
			if opcode == 0x00BD or opcode == 0x00BE:
				style = cxt.pop()
			else:
				style = None
			if opcode == 0x00BC or opcode == 0x00BE:
				color = cxt.pop()
			else:
				color = None
			cxt.put_statement(LineStatement(_from, to, color, ['', 'B', 'BF'][mode], style))
		elif opcode == 0x00BF:
			cxt.put_statement(AssignmentStatement(None, None, keyword = 'LET'))
		elif opcode == 0x00C0:
			flags = read16(file)
			arg = cxt.pop()
			stm = cxt.add_statement(InputStatement)
			stm.arguments.append(arg)
			stm.kind = 'LINE INPUT'
			if (flags & 0x0002) != 0:
				stm.starts_with_semicolon = True
			if (flags & 0x0004) != 0:
				stm.specification = cxt.pop()
		elif opcode == 0x00C2:
			flags = read16(file)
			if (flags & 0x8002) == 0x0002:
				end = cxt.pop()
			else:
				end = None
			if (flags & 0x0002) == 0x0002:
				start = cxt.pop()
				if (flags & 0x4000) == 0x4000:
					start = None # implicit 1
			else:
				start = None
			file = cxt.pop()
			cxt.put_statement(LockStatement(file, start, end, unlock = False))
		elif opcode == 0x00C3:
			cxt.put_statement(PrintStatement("LPRINT"))
		elif opcode == 0x00C4:
			var = cxt.pop()
			source = cxt.pop()
			cxt.put_assignment_statement(AssignmentStatement(var, source, keyword = 'LSET'))
		elif opcode == 0x00C8:
			args = cxt.pop(2)
			cxt.put_assignment_statement(NameStatement(*args))
		elif opcode == 0x00C9 or opcode == 0x00CA:
			flags = read16(file)
			if opcode == 0x00CA:
				length = cxt.pop()
			else:
				length = None
			filename, filenumber = cxt.pop(2)

			if (flags & 0x0001) != 0:
				mode = 'INPUT'
			elif (flags & 0x0002) != 0:
				mode = 'OUTPUT'
			elif (flags & 0x0004) != 0:
				mode = 'RANDOM'
			elif (flags & 0x0008) != 0:
				mode = 'APPEND'
			elif (flags & 0x0020) != 0:
				mode = 'BINARY'

			if (flags & 0x0300) == 0x0100:
				access = 'READ'
			elif (flags & 0x0300) == 0x0200:
				access = 'WRITE'
			elif (flags & 0x0300) == 0x0300:
				access = 'READ WRITE'
			else:
				access = None

			if (flags & 0x3000) == 0x1000:
				lock = 'READ WRITE'
			elif (flags & 0x3000) == 0x2000:
				lock = 'WRITE'
			elif (flags & 0x3000) == 0x3000:
				lock = 'READ'
			elif (flags & 0x4000) != 0:
				lock = 'SHARED'
			else:
				lock = None

			cxt.put_assignment_statement(OpenStatement(filename, filenumber, mode, access, lock, length))
		elif opcode == 0x00D0 or opcode == 0x00D1:
			point = cxt.get_argument('from')
			args = cxt.pop(3 if opcode == 0x00D1 else 2)
			cxt.put_statement(PaintStatement(point, *replace_missing(args)))
		elif opcode == 0x00D8 or opcode == 0x00D9:
			coordinates = cxt.get_argument('from')
			if opcode == 0x00D9:
				color = cxt.pop()
			else:
				color = None
			cxt.put_statement(PSetStatement(coordinates, color, keyword = 'PRESET'))
		elif opcode == 0x00DA or opcode == 0x00DB:
			coordinates = cxt.get_argument('from')
			if opcode == 0x00DB:
				color = cxt.pop()
			else:
				color = None
			cxt.put_statement(PSetStatement(coordinates, color, keyword = 'PSET'))
		elif opcode == 0x00E2:
			arg = cxt.pop()
			cxt.put_statement_kind(ReadStatement).variables.append(arg)
		elif opcode == 0x00E3:
			text = reads(file)
			text = self.expand_comment(text)
			cxt.put_statement(RemStatement(text))
		elif opcode == 0x00E6:
			var = cxt.pop()
			source = cxt.pop()
			cxt.put_assignment_statement(AssignmentStatement(var, source, keyword = 'RSET'))
		elif opcode == 0x00F2:
			flags = read16(file)
			if (flags & 0x8002) == 0x0002:
				end = cxt.pop()
			else:
				end = None
			if (flags & 0x0002) == 0x0002:
				start = cxt.pop()
				if (flags & 0x4000) == 0x4000:
					start = None # implicit 1
			else:
				start = None
			file = cxt.pop()
			cxt.put_statement(LockStatement(file, start, end, unlock = True))
		elif opcode == 0x00F3:
			args = cxt.pop(6)
			_from = tuple(args[0:2])
			to = tuple(args[2:4])
			args = replace_missing(args[4:])
			cxt.put_statement(ViewStatement(_from, to, *args, keyword = 'VIEW'))
		elif opcode == 0x00F5:
			cxt.put_statement(ViewPrintStatement())
		elif opcode == 0x00F6:
			args = cxt.pop(2)
			cxt.put_statement(ViewPrintStatement(*args))
		elif opcode == 0x00F7:
			args = cxt.pop(6)
			_from = tuple(args[0:2])
			to = tuple(args[2:4])
			args = replace_missing(args[4:])
			cxt.put_statement(ViewStatement(_from, to, *args, keyword = 'VIEW SCREEN'))
		elif opcode == 0x00F8:
			args = cxt.pop(2)
			args = replace_missing(args)
			cxt.put_statement(BuiltinStatement('WIDTH', *args))
		elif opcode == 0x00FB:
			args = cxt.pop(4)
			_from = tuple(args[0:2])
			to = tuple(args[2:4])
			cxt.put_statement(WindowStatement(_from, to, keyword = 'WINDOW'))
		elif opcode == 0x00FD:
			args = cxt.pop(4)
			_from = tuple(args[0:2])
			to = tuple(args[2:4])
			cxt.put_statement(WindowStatement(_from, to, keyword = 'WINDOW SCREEN'))
		elif opcode == 0x00FE:
			cxt.put_statement(PrintStatement('WRITE'))
		elif opcode == 0x00FF:
			cxt.put_statement_kind(PrintStatement).add_item(UsingClause(cxt.pop()))
		elif opcode == 0x0100:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("+", *args))
		elif opcode == 0x0101:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("AND", *args))
		elif opcode == 0x0102:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("/", *args))
		elif opcode == 0x0103:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("=", *args))
		elif opcode == 0x0104:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("EQV", *args))
		elif opcode == 0x0108:
			arg = cxt.pop()
			dtype = self.get_builtin_type(parameter)
			if isinstance(dtype, StringType):
				raise Exception(f"Invalid opcode parameter: conversion to string")
			cxt.push(ConvertFunction(arg, dtype))
		elif opcode == 0x015E:
			args = cxt.pop(2)
			cxt.push(BinaryOperator(">=", *args))
		elif opcode == 0x015F:
			args = cxt.pop(2)
			cxt.push(BinaryOperator(">", *args))
		elif opcode == 0x0160:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("\\", *args))
		elif opcode == 0x0161:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("IMP", *args))
		elif opcode == 0x0162:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("<=", *args))
		elif opcode == 0x0163:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("<", *args))
		elif opcode == 0x0164:
			cxt.push(DecimalInteger(parameter))
		elif opcode == 0x0165:
			cxt.push(DecimalInteger(read16(file)))
		elif opcode == 0x0166:
			cxt.push(DecimalInteger(read32(file), suffix = '&'))
		elif opcode == 0x0167:
			cxt.push(HexadecimalInteger(read16(file)))
		elif opcode == 0x0168:
			cxt.push(HexadecimalInteger(read32(file), suffix = '&'))
		elif opcode == 0x0169:
			cxt.push(OctalInteger(read16(file)))
		elif opcode == 0x016A:
			cxt.push(OctalInteger(read32(file), suffix = '&'))
		elif opcode == 0x016B:
			cxt.push(FloatLiteral(readf32(file), suffix = '!'))
		elif opcode == 0x016C:
			cxt.push(FloatLiteral(readf64(file), suffix = '#'))
		elif opcode == 0x016D:
			cxt.push(StringLiteral(reads(file)))
		elif opcode == 0x016E:
			arg = cxt.pop()
			cxt.push(Parentheses(arg))
		elif opcode == 0x016F:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("MOD", *args))
		elif opcode == 0x0170:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("*", *args))
		elif opcode == 0x0171:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("<>", *args))
		elif opcode == 0x0172:
			cxt.push(None)
		elif opcode == 0x0173:
			cxt.push(Missing)
		elif opcode == 0x0174:
			arg = cxt.pop()
			cxt.push(UnaryOperator("NOT", arg))
		elif opcode == 0x0175:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("OR", *args))
		elif opcode == 0x0176:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("^", *args))
		elif opcode == 0x0177:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("-", *args))
		elif opcode == 0x0178:
			arg = cxt.pop()
			cxt.push(UnaryOperator("-", arg))
		elif opcode == 0x0179:
			args = cxt.pop(2)
			cxt.push(BinaryOperator("XOR", *args))
		# QB45+
		elif opcode == 0x017A:
			cxt.push(EventSpecification("UEVENT"))
		elif opcode == 0x017C:
			read16(file)
			size = read16(file)
			column = read16(file)
			cxt.put_declaration().set_type(FixedStringType(size)).as_column = column
		elif opcode == 0x017D:
			cxt.put_statement_kind(VariableDeclarationStatement).set_kind('DIM')
			read16(file)
		# QB70+
		elif opcode == 0x017E:
			argcount = read16(file)
			name = cxt.readvar(file)
			dims = cxt.pop(argcount)
			mode = read16(file) # 0015/0016/017C
			if mode == 0x017C:
				read16(file)
				size = read16(file)
				as_type = FixedStringType(size)
			else:
				as_type = self.get_type(cxt, file, read16(file))
			column = read16(file)
			cxt.put_statement(TypeFieldDeclaration(name, as_type, *dims, as_column = column))
		elif opcode == 0x0185:
			cxt.push(CurrencyLiteral(read64(file)))
		elif opcode == 0x0196:
			cxt.put_statement(EventStatement(None, ['OFF', 'ON'][parameter]))
		elif opcode == 0x0198:
			mode = read16(file)
			arg = cxt.pop()
			cxt.put_statement(BuiltinStatement({
				0x0000: 'MOVEFIRST',
				0x0004: 'MOVELAST',
				0x0008: 'MOVENEXT',
				0x000C: 'MOVEPREVIOUS'
			}[mode], arg))
		elif opcode == 0x019A:
			read16(file)
			typename = cxt.readvar(file)
			args = cxt.pop(3)
			cxt.put_statement(OpenIsamStatement(args[0], typename, args[1], args[2]))
		elif opcode == 0x019F:
			mode = read16(file)
			argcount = read16(file)
			args = cxt.pop(argcount)
			cxt.put_statement(BuiltinStatement({
				0x0000: 'SEEKEQ',
				0x0004: 'SEEKGE',
				0x0008: 'SEEKGT',
			}[mode], *args))
		# VBDOS
		elif opcode == 0x01AA:
			typename = cxt.readvar(file)
			arg = cxt.pop()
			cxt.push(TypeOfIsOperator(arg, typename))
		elif opcode == 0x01C1:
			arg = cxt.pop()
			cxt.push(ExternalObject(arg))
		elif opcode == 0x01C2:
			read16(file)
			name = cxt.readvar(file)
			cxt.put_metacommand(MetaCommand("$FORM", name, argument_takes_colon = False))
		elif opcode == 0x01C7 or opcode == 0x01C8:
			cxt.push(None)
		elif opcode == 0x01C9:
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			if method_name == 'PRINT':
				cxt.put_statement(PrintStatement("PRINT", target))
			else:
				cxt.put_statement(MethodSubCall(target, method_name))
		elif opcode == 0x01CA or opcode == 0x01CB:
			args = cxt.pop(1)
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.put_statement(MethodSubCall(target, method_name, *args))
		elif opcode == 0x01CC or opcode == 0x01CF:
			args = cxt.pop(2)
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.put_statement(MethodSubCall(target, method_name, *args))
		elif opcode == 0x01CD:
			args = cxt.pop(3)
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.put_statement(MethodSubCall(target, method_name, *args))
		elif opcode == 0x01CE:
			args = cxt.pop(4)
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.put_statement(MethodSubCall(target, method_name, *args))
		elif opcode == 0x01D0:
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.push(MethodFunctionCall(target, method_name))
		elif opcode == 0x01D1:
			args = cxt.pop(1)
			target = cxt.pop()
			method = read16(file)
			method_name = BasicFileVersionVBDOS.METHOD_NAMES[method]
			cxt.push(MethodFunctionCall(target, method_name, *args))
		else:
			if opcode in BasicFileVersion.BUILTINS:
				elements = BasicFileVersion.BUILTINS[opcode]
				isfun, name, argcount = elements[:3]
				extra_info = elements[3] if len(elements) > 3 else {}

				popargcount = argcount
				if popargcount is None:
					popargcount = read16(file)
				else:
					popargcount = max(0, popargcount)
				if extra_info.get('assignment'):
					popargcount += 1
				args = cxt.pop(popargcount)
				if extra_info.get('double_arguments'):
					args = clear_missing(args)
				for skip in sorted(extra_info.get('missing_arguments', ())):
					args.insert(skip, None)

				if isfun:
					cxt.push(BuiltinFunctionCall(name, *args, implicit_args = argcount == -1))
				elif extra_info.get('assignment'):
					if len(args) > 1:
						args.insert(0, args.pop())
					if len(args) > 0:
						value = args.pop()
					cxt.put_assignment_statement(AssignmentStatement(BuiltinFunctionCall(name, *args, implicit_args = argcount == -1), value))
				else:
					cxt.put_statement(BuiltinStatement(name, *args))
				for count in range(extra_info.get('skipped_words', 0)):
					read16(file)
			else:
				raise Exception(f"Invalid opcode {actual_opcode:04X}")

class BasicFileVersionQB40(BasicFileVersion):
	VERSION_STAMP = 0x0013
	def get_version_stamp(self):
		return BasicFileVersionQB40.VERSION_STAMP

	def get_header_size(self):
		return 0x0E

	def get_default_procedure_offset(self):
		return 0x82

	def get_maximum_opcode(self):
		return 0x01AF

	def get_maximum_builtin_type(self):
		return 5

	def get_builtin_type(self, index):
		if index == 1:
			return IntegerType()
		elif index == 2:
			return LongType()
		elif index == 3:
			return SingleType()
		elif index == 4:
			return DoubleType()
		elif index == 5:
			return StringType()
		else:
			raise Exception("Invalid built-in type")

	def parse_opcode(self, cxt, file, opcode):
		parameter = opcode >> 9
		opcode &= 0x1FF
		if opcode > self.get_maximum_opcode():
			raise Exception(f"Invalid opcode {opcode:04X}")
		if opcode <= 0x000A:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, opcode, parameter, actual_opcode = opcode)
		elif 0x000B <= opcode <= 0x0010:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x000B, opcode - 0x000B, actual_opcode = opcode)
		elif 0x0011 <= opcode <= 0x0016:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x000C, opcode - 0x0011, actual_opcode = opcode)
		elif 0x0017 <= opcode <= 0x001C:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x000D, opcode - 0x0017, actual_opcode = opcode)
		elif 0x001D <= opcode <= 0x0022:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x000E, opcode - 0x001D, actual_opcode = opcode)
		elif 0x0023 <= opcode <= 0x0028:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x000F, opcode - 0x0023, actual_opcode = opcode)
		elif 0x0029 <= opcode <= 0x002E:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0010, opcode - 0x0029, actual_opcode = opcode)
		elif 0x002F <= opcode <= 0x0034:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0011, opcode - 0x002F, actual_opcode = opcode)
		elif 0x0035 <= opcode <= 0x003A:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0012, opcode - 0x0035, actual_opcode = opcode)
		elif 0x003B <= opcode <= 0x0041:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, opcode - 0x003B + 0x0015, parameter, actual_opcode = opcode)
		elif opcode == 0x0042:
			cxt.get_statement(VariableDeclarationStatement).set_kind('DIM')
		elif opcode == 0x0044:
			arg = cxt.pop()
			# convert ArrayElement to a declaration
			args = arg.args
			name = arg.name
			if parameter != 0:
				name.suffix = self.get_builtin_type(parameter)
			cxt.put_declaration().set_name(name, args)
			cxt.get_statement(VariableDeclarationStatement).set_kind('DIM')
		elif 0x0045 <= opcode <= 0x0130:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, opcode - 0x0045 + 0x001C, parameter, actual_opcode = opcode)
		elif opcode == 0x0131:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0108, parameter = 4, actual_opcode = opcode)
		elif opcode == 0x0132:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0109, parameter, actual_opcode = opcode)
		elif opcode == 0x0133:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0108, parameter = 1, actual_opcode = opcode)
		elif opcode == 0x0134:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0108, parameter = 2, actual_opcode = opcode)
		elif opcode == 0x0135:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x010A, parameter, actual_opcode = opcode)
		elif opcode == 0x0136:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x010B, parameter, actual_opcode = opcode)
		elif opcode == 0x0137:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0108, parameter = 3, actual_opcode = opcode)
		elif 0x0138 <= opcode <= 0x018F:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, opcode - 0x0138 + 0x010C, parameter, actual_opcode = opcode)
		elif 0x0190 <= opcode <= 0x019A:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, 0x0164, parameter = opcode - 0x0190, actual_opcode = opcode)
		elif 0x019B <= opcode <= 0x01AF:
			super(BasicFileVersionQB40, self).parse_opcode(cxt, file, opcode - 0x019B + 0x0165, parameter, actual_opcode = opcode)
		else:
			raise Exception(f"Invalid opcode {opcode:04X}")

class BasicFileVersionQB45(BasicFileVersion):
	VERSION_STAMP = 0x0100
	def get_version_stamp(self):
		return BasicFileVersionQB45.VERSION_STAMP

	def get_header_size(self):
		return 0x1C

	def get_maximum_opcode(self):
		return 0x017D

	def get_maximum_builtin_type(self):
		return 5

	def get_builtin_type(self, index):
		if index == 1:
			return IntegerType()
		elif index == 2:
			return LongType()
		elif index == 3:
			return SingleType()
		elif index == 4:
			return DoubleType()
		elif index == 5:
			return StringType()
		else:
			raise Exception("Invalid built-in type")

class BasicFileVersionQB70(BasicFileVersion):
	VERSION_STAMP = 0x0101
	def get_version_stamp(self):
		return BasicFileVersionQB70.VERSION_STAMP

	def get_header_size(self):
		return 0x1D

	def get_maximum_opcode(self):
		return 0x01A7

	def get_maximum_builtin_type(self):
		return 6

	def get_builtin_type(self, index):
		if index == 1:
			return IntegerType()
		elif index == 2:
			return LongType()
		elif index == 3:
			return SingleType()
		elif index == 4:
			return DoubleType()
		elif index == 5:
			return CurrencyType()
		elif index == 6:
			return StringType()
		else:
			raise Exception("Invalid built-in type")

class BasicFileVersionQB71(BasicFileVersion):
	VERSION_STAMP = 0x0102
	def get_version_stamp(self):
		return BasicFileVersionQB71.VERSION_STAMP

	def get_header_size(self):
		return 0x1D

	def get_maximum_opcode(self):
		return 0x01A8

	def get_maximum_builtin_type(self):
		return 6

	def get_builtin_type(self, index):
		if index == 1:
			return IntegerType()
		elif index == 2:
			return LongType()
		elif index == 3:
			return SingleType()
		elif index == 4:
			return DoubleType()
		elif index == 5:
			return CurrencyType()
		elif index == 6:
			return StringType()
		else:
			raise Exception("Invalid built-in type")

class BasicFileVersionVBDOS(BasicFileVersion):
	VERSION_STAMP = 0x0108

	METHOD_NAMES = {
		0x0000: "ADDITEM",
		0x0001: "CLS",
		0x0002: "HIDE",
		0x0003: "MOVE",
		0x0004: "PRINT",
		0x0005: "PRINTFORM",
		0x0006: "REFRESH",
		0x0007: "REMOVEITEM",
		0x0008: "SETFOCUS",
		0x0009: "SHOW",
		0x000C: "DRAG",
		0x000D: "CLEAR",
		0x000E: "ENDDOC",
		0x0010: "NEWPAGE",
		0x0011: "SETTEXT",
		0x010A: "TEXTHEIGHT",
		0x010B: "TEXTWIDTH",
		0x010F: "GETTEXT",
	}

	def get_version_stamp(self):
		return BasicFileVersionVBDOS.VERSION_STAMP

	def get_header_size(self):
		return 0x20 # plus additional values

	def get_default_procedure_offset(self):
		return 0x56

	def get_maximum_opcode(self):
		return 0x01D1

	def get_maximum_builtin_type(self):
		return 7

	def get_builtin_type(self, index):
		if index == 1:
			return IntegerType()
		elif index == 2:
			return LongType()
		elif index == 3:
			return SingleType()
		elif index == 4 or index == 6:
			return DoubleType()
		elif index == 5:
			return CurrencyType()
		elif index == 7:
			return StringType()
		else:
			raise Exception("Invalid built-in type")

	def parse_form_layout(self, qbfile, file):
		global VBDOS_CONTROL_TYPES

		file.seek(0x16, os.SEEK_SET)
		form_flags = read8(file)
		file.seek(5, os.SEEK_CUR)
		names_offset = read16(file)
		records_length = read16(file)
		records_offset = file.tell()

		file.seek(0x16 + names_offset, os.SEEK_SET)
		Names = []
		while True:
			Name_offset = file.tell()
			unknown_offset = read16(file)
			ctltype = read8(file)
			length = read8(file)
			Name = file.read(length).decode('cp437')
			Names.append((Name, Name_offset, unknown_offset, ctltype))
			if unknown_offset == 0:
				break

		controls = {}

		file.seek(records_offset, os.SEEK_SET)
		while file.tell() + 2 < records_offset + records_length: # if only 2 bytes are left, ignore
			ctloffset = file.tell()

			try:
				index = read8(file)
				ctltype = read8(file)
				ctltype_name, ctltype_length, ctltype_fields = VBDOS_CONTROL_TYPES[ctltype]
				Name, Name_offset, unknown_offset, ctltype2 = Names[index]
			except:
				# if accessing the control type and name fails, probably end of structures
				break

			if ctloffset + ctltype_length > records_offset + records_length:
				# if record type goes beyond the limit, probably end of structures
				break

			if ctltype_name == 'Form' and (form_flags & 0x04) != 0:
				ctltype_name = 'MDIForm'

			control = Object(Name, ctltype_name)

			file.seek(ctloffset + 2, os.SEEK_SET)

			for field in ctltype_fields:
				if type(field) is int:
					file.seek(field, os.SEEK_CUR)
				else:
					size, datatype, name = field
					if size == 1:
						value = read8(file)
					elif size == 2:
						value = read16(file)
					else:
						assert False
					if datatype == 'BOOLEAN' and type(name) is list:
						for bitindex, bitname in enumerate(name):
							if bitname is not None:
								control.attributes[bitname] = Attribute(bitname, datatype, -1 if ((value >> bitindex) & 1) != 0 else 0)
					elif datatype == 'STRING':
						offset = file.tell()
						file.seek(0x16 + value, os.SEEK_SET)
						value = reads(file)
						file.seek(offset, os.SEEK_SET)
						control.attributes[name] = Attribute(name, datatype, value)
					else:
						if datatype != 'UNSIGNED':
							if size == 1 and (value & 0x80) != 0:
								value = (value & 0xFF) - 0x100
							elif size == 2 and (value & 0x8000) != 0:
								value = (value & 0xFFFF) - 0x10000
						control.attributes[name] = Attribute(name, datatype, value)

			file.seek(ctloffset + ctltype_length, os.SEEK_SET)

			if 'WindowState' in control.attributes:
				# the interpretation of the Left/Top/Heigh/Width properties for Forms depends on the WindowState
				if control.attributes['WindowState'].value == 0:
					control.attributes['Left']   = Attribute('Left',   'CHAR', control.attributes['*Left'].value)
					control.attributes['Top']    = Attribute('Top',    'CHAR', control.attributes['*Top'].value)
					control.attributes['Height'] = Attribute('Height', 'CHAR', control.attributes['*Height'].value)
					control.attributes['Width']  = Attribute('Width',  'CHAR', control.attributes['*Width'].value)
				elif control.attributes['WindowState'].value == 1:
					control.attributes['Left']   = Attribute('Left',   'CHAR', 3) # seems to be the default
					control.attributes['Top']    = Attribute('Top',    'CHAR', 22) # seems to be the default
					control.attributes['Height'] = Attribute('Height', 'CHAR', control.attributes['&Height'].value + 2)
					control.attributes['Width']  = Attribute('Width',  'CHAR', control.attributes['&Width'].value + 2)
				elif control.attributes['WindowState'].value == 2:
					control.attributes['Left']   = Attribute('Left',   'CHAR', 0)
					control.attributes['Top']    = Attribute('Top',    'CHAR', 0)
					control.attributes['Height'] = Attribute('Height', 'CHAR', control.attributes['&Height'].value + 2)
					control.attributes['Width']  = Attribute('Width',  'CHAR', control.attributes['&Width'].value + 2)

			if '&Index' in control.attributes and 'Index' in control.attributes and control.attributes['&Index'].value == 0:
				# not a control array, hide Index
				control.attributes['Index'].present = False

			if ctltype_name == 'MDIForm':
				control.attributes['WindowState'].present = False

			if ctltype_name == 'Menu' and ord('\t') in control.attributes['Caption'].value:
				# parse the shortcut string
				control.attributes['Caption'].value, shortcut_text = control.attributes['Caption'].value.split(b'\t')
				shortcut_text = shortcut_text.decode('cp437')
				value = ''
				if shortcut_text.startswith('Shift+'):
					value += '+'
					shortcut_text = shortcut_text[len('Shift+'):]
				if shortcut_text.startswith('Ctrl+'):
					value += '^'
					shortcut_text = shortcut_text[len('Ctrl+'):]
				if shortcut_text.startswith('F'):
					value += '{' + shortcut_text + '}'
				else:
					value += shortcut_text
				control.attributes['Shortcut'] = Attribute('Shortcut', 'SHORTCUT', value)

			if len(controls) == 0:
				qbfile.main_form = control
			controls[ctloffset] = control

		for control in controls.values():
			if '~' in control.attributes and control.attributes['~'].value != 0:
				controls[0x16 + control.attributes['~'].value].members.append(control)

	def parse_header(self, qbfile, file):
		file.seek(0x14, os.SEEK_SET)
		header_extra = read16(file)
		qbfile.header_size += header_extra
		if header_extra > 0:
			self.parse_form_layout(qbfile, file)
		super(BasicFileVersionVBDOS, self).parse_header(qbfile, file)

class QBParseContext:
	def __init__(self, qbfile):
		self.qbfile = qbfile
		self.stack = []
		self.positional_arguments = {}
		self.deffns = []

	def clear(self):
		self.stack.clear()
		self.positional_arguments.clear()

	def push(self, *values):
		self.stack += values

	def pop(self, count = None):
		if count is None:
			return self.stack.pop()
		elif count > 0:
			args = self.stack[-count:]
			self.stack[-count:] = []
			return args
		else:
			return []

	def set_argument(self, position, value):
		assert position not in self.positional_arguments
		self.positional_arguments[position] = value

	def get_argument(self, position):
		return self.positional_arguments.get(position)

	def begin_line(self, label = None, indent = 0):
		self.qbfile.procedures[-1].lines.append(Line(EmptyStatement(), label = label, indent = indent))

	def new_statement(self, at_column = None):
		self.qbfile.procedures[-1].lines[-1].add_statement(EmptyStatement(), at_column = at_column)

	def put_statement(self, statement, into = None):
		if into is None:
			value = self.qbfile.procedures[-1].lines[-1].statements[-1]
		elif isinstance(into, LineIfStatement):
			if into.else_branch is None:
				value = into.then_branch
			else:
				value = into.else_branch.action

		if isinstance(value, EmptyStatement):
			pass
		elif isinstance(value, ErrorInLine) and value.rest_of_line is None:
			value.rest_of_line = statement
			return True
		elif isinstance(value, LineIfStatement):
			success = self.put_statement(statement, into = value)
			if success:
				return True
			if value.else_branch is None and isinstance(statement, ElseStatement):
				value.else_branch = statement
				return True
			raise Exception("Statements cannot be combined")
		else:
			if into is not None:
				return False
			raise Exception("Statements cannot be combined")

		if into is None:
			self.qbfile.procedures[-1].lines[-1].statements[-1] = statement
		elif isinstance(into, LineIfStatement):
			if into.else_branch is None:
				into.then_branch = statement
			else:
				into.else_branch.action = statement
		return True

	def peek_statement(self, statement_class):
		if not isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], statement_class):
			return None
		return self.qbfile.procedures[-1].lines[-1].statements[-1]

	def get_statement(self, statement_class):
		if not isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], statement_class):
			raise Exception("Invalid statement")
		return self.qbfile.procedures[-1].lines[-1].statements[-1]

	def add_statement(self, statement_class):
		if not isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], statement_class):
			self.put_statement(statement_class())
		return self.qbfile.procedures[-1].lines[-1].statements[-1]

	def put_assignment_statement(self, statement):
		if isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], ConstDeclaration):
			self.qbfile.procedures[-1].lines[-1].statements[-1].assignments.append(statement)
		elif isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], AssignmentStatement) \
		and self.qbfile.procedures[-1].lines[-1].statements[-1].keyword == 'LET' \
		and self.qbfile.procedures[-1].lines[-1].statements[-1].target is None \
		and self.qbfile.procedures[-1].lines[-1].statements[-1].value is None:
			self.qbfile.procedures[-1].lines[-1].statements[-1] = statement
			statement.keyword = 'LET'
		else:
			self.put_statement(statement)

	def put_declaration(self):
		d = self.put_statement_kind(VariableDeclarationStatement)
		if len(d.declarations) == 0 or d.declarations[-1].name is not None:
			d.declarations.append(VariableDeclaration(None, None))
		return d.declarations[-1]

	def put_statement_kind(self, statement_class, *args, **kwds):
		if not isinstance(self.qbfile.procedures[-1].lines[-1].statements[-1], statement_class):
			self.put_statement(statement_class(*args, **kwds))
		return self.qbfile.procedures[-1].lines[-1].statements[-1]

	def begin_deffn(self, deffn):
		self.put_statement(deffn)
		self.deffns.append(deffn)

	def end_deffn(self, element):
		if isinstance(element, EndDeclaration) and element.kind == 'DEF':
			self.put_statement(element)
		else:
			if len(self.deffns) > 0:
				self.deffns[-1].definition = element
			else:
				assert False

		if len(self.deffns) > 0:
			self.deffns.pop()
		else:
			assert False

	def get_exit_kind(self):
		if len(self.deffns) > 0:
			return 'DEF'
		else:
			return self.qbfile.procedures[-1].kind

	def put_metacommand(self, cmd):
		statement = self.qbfile.procedures[-1].lines[-1].statements[-1]
		if isinstance(statement, ErrorInLine):
			# apparently an error-in-line may prefix a comment?
			statement = statement.rest_of_line

		if isinstance(statement, RemStatement):
			assert statement.metacommand is None
			statement.metacommand = cmd
		else:
			assert self.qbfile.procedures[-1].lines[-1].comment is not None
			assert self.qbfile.procedures[-1].lines[-1].comment.metacommand is None
			self.qbfile.procedures[-1].lines[-1].comment.metacommand = cmd

	def readvar(self, file):
		name_offset = read16(file)
		return self.qbfile.readvar(file, name_offset)

class BasicFile:
	VERSIONS = {
		'40': BasicFileVersionQB40,
		'45': BasicFileVersionQB45,
		'70': BasicFileVersionQB70,
		'71': BasicFileVersionQB71,
		'vb': BasicFileVersionVBDOS,
	}
	def __init__(self, version):
		if type(version) is str:
			version = BasicFile.VERSIONS[version.lower()]()
		assert isinstance(version, BasicFileVersion)
		self.version = version
		self.variables = {} # name to offset
		self.variable_names = {} # offsets to names
		self.last_variable_offset = 0x56
		self.procedures_offset = self.version.get_default_procedure_offset()
		self.header_size = self.version.get_header_size()
		self.procedures = [Procedure()]
		self.main_form = None # only for VBDOS
		self.parse_context = QBParseContext(self)

	def __repr__(self):
		return self.__class__.__name__ + repr(self.__dict__)

	def add_variable(self, name):
		var = Identifier(name, self.last_variable_offset)
		self.variables[var.name] = self.last_variable_offset
		self.variable_names[self.last_variable_offset] = var.name
		if type(var.name) is int:
			length = 6
		else:
			length= 4 + len(var.name)
		self.last_variable_offset += length
		self.procedures_offset += length
		return var

	@staticmethod
	def parse_binary(file):
		signature = read8(file)
		if signature != 0xFC:
			raise Exception("Invalid signature")
		version_number = read16(file)
		version = {
			BasicFileVersionQB40.VERSION_STAMP:  BasicFileVersionQB40,
			BasicFileVersionQB45.VERSION_STAMP:  BasicFileVersionQB45,
			BasicFileVersionQB70.VERSION_STAMP:  BasicFileVersionQB70,
			BasicFileVersionQB71.VERSION_STAMP:  BasicFileVersionQB71,
			BasicFileVersionVBDOS.VERSION_STAMP: BasicFileVersionVBDOS,
		}.get(version_number)
		if version is None:
			raise Exception("Invalid file version")
		qbfile = BasicFile(version())
		try:
			qbfile.parse_versioned_binary(file)
		except Exception as e:
			#print(e)
			print(traceback.format_exc())
		return qbfile

	def parse_versioned_binary(self, file):
		self.procedures[:] = [Procedure()]
		file.seek(0, os.SEEK_END)
		end = file.tell()
		self.version.parse_header(self, file)
		file.seek(self.header_size + self.procedures_offset, os.SEEK_SET)
		self.version.parse_opcodes(self.parse_context, file)
		while file.tell() + 16 < end:
			file.seek(16, os.SEEK_CUR)
			file.read(1)
			procedure_name_length = read16(file)
			procedure_name = file.read(procedure_name_length)
			file.read(2)
			flags = read8(file)
			self.procedures.append(Procedure(procedure_name, static = (flags & 0x80) != 0))
			self.version.parse_opcodes(self.parse_context, file)

	def readvar(self, file, name_offset):
		if name_offset in self.variable_names:
			return Identifier(self.variable_names[name_offset], name_offset)
		current = file.tell()
		file.seek(self.header_size + name_offset + 2, os.SEEK_SET)
		flags = read8(file)
		length = read8(file)
		if (flags & 0x02) != 0 and length == 2:
			name = read16(file)
		else:
			name = file.read(length)

		self.variables[name] = name_offset
		self.variable_names[name_offset] = name
		#self.last_variable_offset = 0x56 # TODO: update?

		file.seek(current, os.SEEK_SET)
		return Identifier(name, name_offset)

	def print(self, file = None, **kwds):
		if self.main_form is not None:
			print("Version 1.00", file = file)
			self.main_form.print(file = file)
		for procedure in self.procedures:
			if procedure.kind is not None:
				print(file = file)
			procedure.print(file = file, **kwds)

def main():
	with open(sys.argv[1], 'rb') as file:
		qbfile = BasicFile.parse_binary(file)
		#print(qbfile)
		qbfile.print()

if __name__ == '__main__':
	main()

