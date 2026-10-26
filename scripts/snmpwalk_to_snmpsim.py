"""
The purpose of this script is to clean up a SNMP walk taken with Net-SNMP tools so it can be used by SNMPSIM.
The result is written as a cleaned SNMP walk or, when the output file ends with '.snmprec' (or --format snmprec is used),
as a snmprec file. The snmprec conversion requires the snmpsim package (see requirements.txt).

The following issues are fixed:
- Encoding: the file is decoded using its byte order mark (e.g. UTF-16 files created with a PowerShell redirection),
  as UTF-8 or as Latin-1 (in that order). The output is written in UTF-8
- Values spanning several lines (e.g. a sysDescr with line breaks or a wrapped Hex-STRING) are joined into one record
- STRING values containing line breaks, control characters or non-ASCII characters are written as Hex-STRING,
  so SNMPSIM returns the same bytes as the device
- Non-printable characters in other records are removed
- INTEGER and Gauge32 values formatted with a DISPLAY-HINT (e.g. '5.3 TenthdBmV') are converted to the raw value (53)
- Records without a value ('No Such Object', 'No Such Instance', 'No more variables left in this MIB View') are removed
- Lines that are not part of a SNMP record (e.g. 'End of MIB') are removed
"""

__version__ = '2.0'
__author__ = 'Miguel Obregon'

import argparse		# Argument parser used to pass arguments to the scripts
import codecs		# Byte order marks
import re			# Regular Expressions
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Constants
targetFormat = 'utf-8'

OUTPUT_FORMATS = ('auto', 'snmpwalk', 'snmprec')

# The UTF-32 byte order marks must be checked before the UTF-16 ones (same prefix)
BYTE_ORDER_MARKS = (
	(codecs.BOM_UTF32_LE, 'utf-32'),
	(codecs.BOM_UTF32_BE, 'utf-32'),
	(codecs.BOM_UTF8, 'utf-8-sig'),
	(codecs.BOM_UTF16_LE, 'utf-16'),
	(codecs.BOM_UTF16_BE, 'utf-16'),
)

# A SNMP record starts with a numeric OID ('.1.3.6.', '1.3.6.' or 'iso.3.6.') followed by ' = '
RECORD_START = re.compile(r'^(?:\.?1|iso)(?P<oid>\.3\.6(?:\.\d+)*) =(?: (?P<value>.*))?$', re.DOTALL)

# A SNMP record using a MIB name instead of a numeric OID (e.g. 'SNMPv2-MIB::sysDescr.0 = STRING: ...')
SYMBOLIC_RECORD = re.compile(r'^[A-Za-z][\w-]*::\S+ =')

# Messages printed by Net-SNMP tools that are not part of a SNMP record
NON_RECORD_LINE = re.compile(r'^(?:End of MIB\s*$|Timeout: No Response from )')

# Values returned by the agent when there is no value for the OID
EXCEPTION_VALUES = (
	'No Such Object available on this agent at this OID',
	'No Such Instance currently exists at this OID',
	'No more variables left in this MIB View',
)

# INTEGER/Gauge32 value formatted with a DISPLAY-HINT 'd-N' (e.g. 'INTEGER: 5.3 TenthdBmV').
# Net-SNMP always prints N decimals, so removing the decimal point gives the raw value
DISPLAY_HINT_NUMBER = re.compile(r'^(?P<tag>INTEGER|Gauge32): (?P<number>-?\d+\.\d+)(?:\s.*)?$', re.DOTALL)

# Record types whose values can be wrapped over several lines by Net-SNMP (hexadecimal bytes)
HEX_TAGS = ('Hex-STRING', 'BITS', 'Opaque')


class WalkConversionError(Exception):
	"""
	Raised when a SNMP walk cannot be converted
	"""
	pass


@dataclass
class WalkCleanResult:
	"""
	Result of cleaning a SNMP walk

	Attributes
	----------
		lines: list
			The cleaned SNMP records (one record per item, without line break)
		messages: list
			Information about the records that were changed or removed
	"""
	lines: List[str] = field(default_factory=list)
	messages: List[str] = field(default_factory=list)


@dataclass
class WalkConversionResult:
	"""
	Result of converting a SNMP walk

	Attributes
	----------
		content: str
			The content of the converted file
		outputFormat: str
			The format of the converted file ('snmpwalk' or 'snmprec')
		recordCount: int
			The number of records in the converted file
		messages: list
			Information about the records that were changed or removed
	"""
	content: str
	outputFormat: str
	recordCount: int
	messages: List[str] = field(default_factory=list)


def decodeWalk(data: bytes) -> Tuple[str, str]:
	"""
	Decode the content of a SNMP walk

	Parameters
	----------
	data: bytes
		Raw content of the SNMP walk

	Returns
	-------
		A tuple with the decoded text and the name of the encoding that was used
	"""
	for byteOrderMark, encoding in BYTE_ORDER_MARKS:
		if data.startswith(byteOrderMark):
			return data.decode(encoding), encoding

	try:
		return data.decode('utf-8'), 'utf-8'
	except UnicodeDecodeError:
		# Latin-1 can decode any byte, so the original bytes are always preserved
		return data.decode('latin-1'), 'latin-1'


def _splitLines(text: str) -> List[str]:
	"""
	Split the text in lines. The line ending of the file (LF or CRLF) is detected from the lines that start a record,
	because values (e.g. a sysDescr) can contain their own line breaks. A carriage return that is not part of the
	line ending is kept as part of the value
	"""
	lines = text.split('\n')

	if lines and lines[-1] == '':
		lines.pop()

	recordLines = [line for line in lines if RECORD_START.match(line)]
	crlfRecordLines = sum(1 for line in recordLines if line.endswith('\r'))

	if crlfRecordLines * 2 > len(recordLines):
		lines = [line[:-1] if line.endswith('\r') else line for line in lines]

	return lines


def _getTag(value: str) -> str:
	"""
	Get the Net-SNMP type of a value (e.g. 'STRING', 'Hex-STRING', 'INTEGER')
	"""
	match = re.match(r'^([A-Za-z][\w -]*?):', value)
	return match.group(1) if match else ''


def _isOpenQuotedString(value: str) -> bool:
	"""
	Check if the value is a quoted STRING whose closing quote was not found yet
	"""
	if not value.startswith('STRING: "'):
		return False

	body = value[len('STRING: '):].rstrip()
	return len(body) < 2 or not body.endswith('"')


def _isPrintableAscii(text: str) -> bool:
	return all(' ' <= character <= '~' for character in text)


def _cleanString(value: str, encoding: str) -> str:
	"""
	Convert a STRING value to Hex-STRING when it contains characters that cannot be kept in a single-line record
	(line breaks, control characters) or that SNMPSIM would drop (non-ASCII characters)

	Parameters
	----------
	value: str
		The value of the record (e.g. 'STRING: "Linux"')
	encoding: str
		The encoding used to convert the characters back to bytes
	"""
	body = value[len('STRING:'):]
	if body.startswith(' '):
		body = body[1:]

	trimmed = body.rstrip()
	if len(trimmed) >= 2 and trimmed.startswith('"') and trimmed.endswith('"'):
		content = trimmed[1:-1]
	elif trimmed.startswith('"'):
		# Quote not closed (e.g. truncated file)
		content = trimmed[1:]
	else:
		content = trimmed

	if _isPrintableAscii(content):
		return 'STRING: ' + trimmed

	return 'Hex-STRING: ' + ' '.join('{:02X}'.format(byte) for byte in content.encode(encoding))


def cleanWalk(text: str, encoding: str = 'utf-8') -> WalkCleanResult:
	"""
	Clean the records of a SNMP walk taken with Net-SNMP tools

	Parameters
	----------
	text: str
		The decoded SNMP walk
	encoding: str
		The encoding that was used to decode the SNMP walk. It is used to convert STRING values back to bytes

	Returns
	-------
		A WalkCleanResult with the cleaned records and information about the records that were changed or removed
	"""
	valueEncoding = 'latin-1' if encoding == 'latin-1' else 'utf-8'
	result = WalkCleanResult()

	# Messages about specific lines: (line number, message)
	lineMessages = []

	# Join the lines that belong to the same record. Each item: [line number, OID, value]
	records = []
	current = None

	for lineNumber, line in enumerate(_splitLines(text), start=1):

		match = RECORD_START.match(line)
		if match:
			current = [lineNumber, '.1' + match.group('oid'), match.group('value') or '']
			records.append(current)
			continue

		# Inside a quoted STRING every line (even an empty one) is part of the value
		if current is not None and _isOpenQuotedString(current[2]):
			current[2] += '\n' + line
			continue

		if not line.strip():
			continue

		if NON_RECORD_LINE.match(line):
			lineMessages.append((lineNumber, 'Line[{}]: Not a SNMP record, removed: {}'.format(lineNumber, line.strip())))
			continue

		if SYMBOLIC_RECORD.match(line):
			lineMessages.append((lineNumber, 'Line[{}]: Record without a numeric OID removed (take the walk with snmpwalk -On): {}'.format(lineNumber, line.strip())))
			current = None
			continue

		if current is None:
			lineMessages.append((lineNumber, 'Line[{}]: Not a SNMP record, removed: {}'.format(lineNumber, line.strip())))
			continue

		tag = _getTag(current[2])
		if tag == 'STRING':
			current[2] += '\n' + line
		elif tag in HEX_TAGS:
			current[2] = current[2].rstrip() + ' ' + line.strip()
		else:
			lineMessages.append((lineNumber, 'Line[{}]: Unexpected text after the record of line {}, removed: {}'.format(lineNumber, current[0], line.strip())))

	if not records:
		raise WalkConversionError('No SNMP records found. Was the walk taken with numeric OIDs (snmpwalk -On)?')

	hexStringCount = 0
	displayHintCount = 0

	for lineNumber, oid, value in records:

		if any(value.startswith(exceptionValue) for exceptionValue in EXCEPTION_VALUES):
			lineMessages.append((lineNumber, 'Line[{}]: Record without value removed: {} = {}'.format(lineNumber, oid, value.strip())))
			continue

		if _getTag(value) == 'STRING':
			cleanedValue = _cleanString(value, valueEncoding)
			if cleanedValue.startswith('Hex-STRING'):
				hexStringCount += 1
		else:
			cleanedValue = value.strip()

			printableValue = ''.join(character for character in cleanedValue if character.isprintable())
			if printableValue != cleanedValue:
				lineMessages.append((lineNumber, 'Line[{}]: Non-printable characters removed from {}'.format(lineNumber, oid)))
				cleanedValue = printableValue

			displayHint = DISPLAY_HINT_NUMBER.match(cleanedValue)
			if displayHint:
				cleanedValue = '{}: {}'.format(displayHint.group('tag'), int(displayHint.group('number').replace('.', '')))
				displayHintCount += 1

		result.lines.append('{} = {}'.format(oid, cleanedValue))

	result.messages = [message for _, message in sorted(lineMessages, key=lambda item: item[0])]

	if hexStringCount:
		result.messages.append('{} STRING value(s) with line breaks, control or non-ASCII characters written as Hex-STRING'.format(hexStringCount))

	if displayHintCount:
		result.messages.append('{} INTEGER/Gauge32 value(s) with a DISPLAY-HINT (e.g. TenthdBmV) converted to the raw value'.format(displayHintCount))

	return result


def walkToSnmprec(lines: List[str]) -> Tuple[List[str], List[str]]:
	"""
	Convert cleaned SNMP walk records to snmprec records using the snmpsim parser.
	The records are sorted by OID (required by SNMPSIM to answer GETNEXT/GETBULK requests) and duplicates are removed

	Parameters
	----------
	lines: list
		The cleaned SNMP walk records (see cleanWalk)

	Returns
	-------
		A tuple with the snmprec records and information about the records that were skipped
	"""
	try:
		from snmpsim.record import snmprec, walk
	except ImportError as exception:
		raise WalkConversionError('The snmprec output requires the snmpsim package (pip install -r requirements.txt): {}'.format(exception))

	walkRecord = walk.WalkRecord()
	snmprecRecord = snmprec.SnmprecRecord()
	messages = []
	parsedRecords = []

	for line in lines:
		try:
			parsedRecords.append(walkRecord.evaluate(line.encode('ascii', 'ignore')))
		except Exception as exception:
			messages.append('Record skipped, it could not be converted to snmprec: {} ({})'.format(line, str(exception).strip()))

	# The sort is stable, so the first occurrence of a duplicated OID is kept
	parsedRecords.sort(key=lambda record: record[0])

	snmprecLines = []
	previousOid = None

	for oid, value in parsedRecords:
		if oid == previousOid:
			messages.append('Duplicated record skipped: {}'.format(oid))
			continue

		previousOid = oid
		snmprecLines.append(snmprecRecord.format(oid, value).decode('latin-1').rstrip('\n'))

	return snmprecLines, messages


def resolveOutputFormat(outputPath: Optional[str], outputFormat: str = 'auto') -> str:
	"""
	Get the output format ('snmpwalk' or 'snmprec'). With 'auto', the format is based on the extension of the output file
	"""
	if outputFormat not in OUTPUT_FORMATS:
		raise WalkConversionError('Unknown output format: {}'.format(outputFormat))

	if outputFormat != 'auto':
		return outputFormat

	return 'snmprec' if outputPath and outputPath.lower().endswith('.snmprec') else 'snmpwalk'


def convertWalk(data: bytes, outputFormat: str = 'snmpwalk') -> WalkConversionResult:
	"""
	Convert the raw content of a SNMP walk to a cleaned SNMP walk or to a snmprec file

	Parameters
	----------
	data: bytes
		Raw content of the SNMP walk
	outputFormat: str
		'snmpwalk' or 'snmprec'

	Returns
	-------
		A WalkConversionResult with the content of the converted file
	"""
	outputFormat = resolveOutputFormat(None, outputFormat)

	text, encoding = decodeWalk(data)
	cleanResult = cleanWalk(text, encoding)
	messages = list(cleanResult.messages)

	if encoding != 'utf-8':
		messages.insert(0, 'Input decoded as {}'.format(encoding))

	lines = cleanResult.lines
	if outputFormat == 'snmprec':
		lines, snmprecMessages = walkToSnmprec(lines)
		messages.extend(snmprecMessages)

	if not lines:
		raise WalkConversionError('No SNMP records left after the conversion')

	return WalkConversionResult(
		content='\n'.join(lines) + '\n',
		outputFormat=outputFormat,
		recordCount=len(lines),
		messages=messages
	)


def convertWalkFile(inputPath: str, outputPath: str, outputFormat: str = 'auto') -> WalkConversionResult:
	"""
	Convert a SNMP walk file. The output file is created or overwritten

	Parameters
	----------
	inputPath: str
		File path of the SNMP walk
	outputPath: str
		File path of the converted file
	outputFormat: str
		'auto' (based on the extension of outputPath), 'snmpwalk' or 'snmprec'
	"""
	with open(inputPath, mode='rb') as inputFile:
		data = inputFile.read()

	result = convertWalk(data, resolveOutputFormat(outputPath, outputFormat))

	with open(outputPath, mode='w', encoding=targetFormat, newline='') as outputFile:
		outputFile.write(result.content)

	return result


def main(argv: Optional[List[str]] = None) -> int:

	# Create the parser object
	parser = argparse.ArgumentParser(description='Clean up a SNMP walk taken with Net-SNMP tools and convert it to a file that can be used by SNMPSIM (cleaned SNMP walk or snmprec file)')

	# Define the arguments
	parser.add_argument('-i', '--input', dest='inputFile', required=True, help='File path of the SNMP walk', type=str)
	parser.add_argument('-o', '--output', dest='outputFile', required=True, help='File path of the converted file. It is created or overwritten', type=str)
	parser.add_argument('-f', '--format', dest='outputFormat', choices=OUTPUT_FORMATS, default='auto', help='Format of the converted file. auto (default): snmprec when the output file ends with .snmprec, otherwise a cleaned SNMP walk')

	# Check if no arguments were provided
	if argv is None and len(sys.argv) == 1:
		# If no argument were provided, show help message
		parser.print_help(sys.stderr)
		return 1

	# Process arguments
	arguments = parser.parse_args(argv)

	print('[INFO]|Main|Converting file:{}'.format(arguments.inputFile), flush=True)

	try:
		result = convertWalkFile(arguments.inputFile, arguments.outputFile, arguments.outputFormat)
	except (OSError, WalkConversionError) as exception:
		print('[ERROR]|Main|{}'.format(exception), file=sys.stderr)
		return 1

	for message in result.messages:
		print('[INFO]|Main|{}'.format(message))

	print('[INFO]|Main|{} records written to {} ({} format)'.format(result.recordCount, arguments.outputFile, result.outputFormat))
	return 0


if __name__ == "__main__":
	sys.exit(main())
