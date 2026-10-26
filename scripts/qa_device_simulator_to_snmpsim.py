#!/usr/bin/env python

"""qa_device_simulator_to_snmpsim.py: Convert simulations took from QA Device Simulator (XML file extension) to snmpsim simulations (snmprec extension)"""

__author__		= "Miguel Obregon"
__copyright__	= "Skyline Communications"
__version__		= "2.0.0"
__status__		= "Development"

# Modules
import codecs # Module used to detect byte order marks
import xml.etree.ElementTree # Module used to parse XML files
import os	# Module used to work with OS files and directories
import sys # Module used to work with running application
from argparse import ArgumentParser # Module used to parse arguments
from dataclasses import dataclass, field # Module used to define the result of a conversion
from enum import Enum # Module used to define enumerations
from typing import List, Optional # Type hints
import re # Regular expressions

# +++++
# Enums
# +++++
class OidType(Enum):
	"""
	A Enum class containing all the OID types
	"""
	Integer32 = 2
	OctetString = 4
	Null = 5
	#ObjectIdentifier = 6
	ObjectId = 6
	IPAddress = 64
	IpAddress = 64
	Counter32 = 65
	Gauge32 = 66
	TimeTicks = 67
	Opaque = 68
	Counter64 = 70

def enumContainsName(enumType, name):
	
	"""This function checks if a name is available in the enum type passed as argument

	Arguments
	---------
		enumtype: Enum object
			The enum type
		name: str
			The name to be checked if exists in the enum type

	Returns
	-------
		True if the name exists in the enum type. Otherwise false
	"""

	try:
		enumType[name]
	except Exception:
		return False
	return True

# +++++++
# Classes
# +++++++

class SnmpsimRecord:
	"""
	A class used to represent a SNMP record from SNMPSIM
	

	Attributes
	----------
		oid: str
			The SNMP OID of the SNMP record
		oidType:
			The OID type. The following types are supported:
				Integer32
				OctetString
				Null
				ObjectIdentifier
				IpAddress
				Counter32
				Gauge32
				TimeTicks
				Opaque
				Counter64
		value: str
			The value of the SNMP record
	"""

	def __init__(self, oid:str, oidType:str, value:str) -> None:
		self.__oid = oid
		self.__oidType = oidType
		self.__value = value

	@property
	def oid(self):
		return self.__oid

	@property
	def oidType(self):
		return self.__oidType

	@property
	def value(self):
		return self.__value

class QADeviceSimulatorDefinition:

	"""
	A class used to represent a SNMP record (a.k.a. OID definition) available in the QA Device Simulator file

	Attributes
	----------
		oid: str
			The SNMP OID of the SNMP record
		type: str
			The OID type. The following types are supported:
				Integer32
				OctetString
				Null
				ObjectIdentifier
				IpAddress
				Counter32
				Gauge32
				TimeTicks
				Opaque
				Counter64
		returnValue: str
			The value of the SNMP record. It can be used to define a dynamic behavior in the value returned by the simulation
		logOutput: str
			The output to be displayed in the QA Device Simulator GUI
		comment: str
			A extra comment added to the SNMP record
		delay: bool
			To be defined
		save: bool
			To be defined
		skipOid: bool
			To be defined


	"""
	def __init__(self, oid:str, type:str, returnValue:str, logOutput:str, comment:str, delay = None, save = None, skipOid = None) -> None:
		self.__oid = oid
		self.__type = type
		self.__returnValue = returnValue
		self.__logOutput = logOutput
		self.__comment = comment

		# Validating the 'delay' attribute since it could not be defined in the simulation file
		if (isinstance(delay,str)):
			self.__delay = delay
		else:
			self.__delay = "NA"
	
		# Validating the 'save' attribute since it could not be defined in the simulation file
		if (isinstance(save,str)):
			self.__save = save
		else:
			self.__save = "NA"

		# Validating the 'skipOid' attribute since it could not be defined in the simulation file
		if (isinstance(skipOid,str)):
			self.__skipOid = skipOid
		else:
			self.__skipOid = "NA"

	@property
	def oid(self):
		return self.__oid

	@property
	def type(self):
		return self.__type

	@property
	def returnValue(self):
		return self.__returnValue
	
	@property
	def logOutput(self):
		return self.__logOutput

	@property
	def comment(self):
		return self.__comment

	@property
	def delay(self):
		return self.__delay

	@property
	def save(self):
		return self.__save
	
	@property
	def skipOid(self):
		return self.__skipOid

# ++++++++++
# Exceptions
# ++++++++++
class EmptyListException(Exception):
	
	"""
	This class implements a custom exception when a list is empty
	"""
	pass

class EmptyStringException(Exception):

	"""
	This class implements a custom exception when a string is empty
	"""
	pass

class ConversionError(Exception):

	"""
	This class implements a custom exception when a simulation file cannot be converted
	"""
	pass

# +++++++++
# Constants
# +++++++++

# Byte order marks used to detect the encoding of the simulation file. UTF-32 must be checked before UTF-16 (same prefix)
BYTE_ORDER_MARKS = (
	(codecs.BOM_UTF32_LE, 'utf-32'),
	(codecs.BOM_UTF32_BE, 'utf-32'),
	(codecs.BOM_UTF8, 'utf-8-sig'),
	(codecs.BOM_UTF16_LE, 'utf-16'),
	(codecs.BOM_UTF16_BE, 'utf-16'),
)

# Encoding defined in the XML declaration (e.g. <?xml version="1.0" encoding="utf-8"?>)
XML_DECLARATION_ENCODING = re.compile(rb'^\s*<\?xml[^>]*?encoding\s*=\s*["\']([A-Za-z0-9._-]+)["\']')

# Character references (e.g. '&#x0;' or '&#20;') and raw characters. Some of them are not allowed in XML 1.0
CHARACTER_REFERENCE = re.compile(r'&#(?:x([0-9A-Fa-f]+)|([0-9]+));')
INVALID_XML_CHARACTER = re.compile('[\x00-\x08\x0B\x0C\x0E-\x1F]')

# The characters that are not allowed in XML 1.0 (e.g. char(0) in a MAC address) are replaced by characters of the
# Unicode private use area before parsing the file and restored after parsing it, so the original value is kept
PLACEHOLDER_OFFSET = 0xE000
RESTORE_INVALID_CHARACTERS = {PLACEHOLDER_OFFSET + codePoint: codePoint for codePoint in range(0x20) if codePoint not in (0x9, 0xA, 0xD)}

# Validation of OIDs and values
OID_PATTERN = re.compile(r'^\d+(?:\.\d+)+$')
SIGNED_INTEGER_PATTERN = re.compile(r'^-?\d+$')
UNSIGNED_INTEGER_PATTERN = re.compile(r'^\d+$')
IP_ADDRESS_PATTERN = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')

# +++++++
# Methods
# +++++++

def DecodeXmlContent(data: bytes, messages: Optional[list] = None) -> str:

	"""Decode the content of a XML file using its byte order mark, the encoding of its XML declaration or UTF-8 (in that order)

	Parameters
	----------
		data: bytes
			The content of the XML file
		messages: list
			Optional list where information about the decoding is added

	Returns
	-------
		The decoded content
	"""

	for byteOrderMark, encoding in BYTE_ORDER_MARKS:
		if data.startswith(byteOrderMark):
			return data.decode(encoding)

	declaration = XML_DECLARATION_ENCODING.match(data)
	encoding = declaration.group(1).decode('ascii') if declaration else 'utf-8'

	try:
		return data.decode(encoding)
	except LookupError:
		raise ConversionError("Unknown encoding in the XML declaration: {}".format(encoding))
	except UnicodeDecodeError:
		if messages is not None:
			messages.append("The file is not valid {}, it was decoded as Latin-1".format(encoding))
		return data.decode('latin-1')

def SanitizeXmlContent(xmlContent: str, messages: Optional[list] = None) -> str:

	"""Replace the characters that are not allowed in XML 1.0 by placeholders, so the XML can be parsed.
	Some XML files generated by the QA Device Simulator contain these characters (e.g. '&#x0;' in a MAC address).
	The placeholders are converted back to the original characters after parsing (see RESTORE_INVALID_CHARACTERS).
	Valid character references, such as a line break ('&#xA;'), are not changed

	Parameters
	----------
		xmlContent: str
			The content of the XML file
		messages: list
			Optional list where information about the replacements is added

	Returns
	-------
		The content that can be parsed
	"""

	replacements = 0

	def replaceReference(match):
		nonlocal replacements
		codePoint = int(match.group(1), 16) if match.group(1) is not None else int(match.group(2))

		if codePoint >= 0x20 or codePoint in (0x9, 0xA, 0xD):
			return match.group(0)

		replacements += 1
		return '&#x{:X};'.format(PLACEHOLDER_OFFSET + codePoint)

	def replaceCharacter(match):
		nonlocal replacements
		replacements += 1
		return '&#x{:X};'.format(PLACEHOLDER_OFFSET + ord(match.group(0)))

	sanitizedContent = CHARACTER_REFERENCE.sub(replaceReference, xmlContent)
	sanitizedContent = INVALID_XML_CHARACTER.sub(replaceCharacter, sanitizedContent)

	if replacements and messages is not None:
		messages.append("{} character(s) not allowed in XML found (e.g. &#x0;). They are kept as the original bytes".format(replacements))

	return sanitizedContent

def ParseQADeviceSimulatorContent(data: bytes, messages: Optional[list] = None) -> List[QADeviceSimulatorDefinition]:

	"""Parse the content of a simulation file generated by the QA Device Simulator

	Parameters
	----------
		data: bytes
			The content of the simulation file
		messages: list
			Optional list where information about the parsing is added

	Returns
	-------
		A list with all the OID definitions found in the simulation file
	"""

	if messages is None:
		messages = []

	xmlContent = SanitizeXmlContent(DecodeXmlContent(data, messages), messages)

	try:
		rootElement = xml.etree.ElementTree.fromstring(xmlContent)
	except xml.etree.ElementTree.ParseError as exception:
		raise ConversionError("The file is not a valid XML file: {}".format(exception))

	# We noticed that depending of the age of simulation, a different XML structure is used.
	listDefinitions = rootElement.findall('./Definitions/Definition')

	if not listDefinitions:
		# Old structure: the OID definitions are available directly under the root element
		listDefinitions = rootElement.findall('./Definition')

	messages.append("Number of OID definitions: {}".format(len(listDefinitions)))

	qaDeviceSimulatorDefinitions = []

	for simulationRecord in listDefinitions:

		attributes = {name: value.translate(RESTORE_INVALID_CHARACTERS) for name, value in simulationRecord.attrib.items()}

		qaDeviceSimulatorDefinitions.append(QADeviceSimulatorDefinition(
			oid = attributes.get('OID', ''),
			type = attributes.get('Type', ''),
			returnValue = attributes.get('ReturnValue', ''),
			logOutput = attributes.get('LogOutput'),
			comment = attributes.get('Comment'),
			# Old simulations don't contain these attributes
			delay = attributes.get('Delay'),
			save = attributes.get('Save'),
			skipOid = attributes.get('SkipOID')
			))

	return qaDeviceSimulatorDefinitions

def ParseQADeviceSimulatorFile(filePath: str, messages: Optional[list] = None) -> List[QADeviceSimulatorDefinition]:

	"""Parse a simulation file generated by the QA Device Simulator

	Parameters
	----------
		filePath: str
			The file path of the simulation file
		messages: list
			Optional list where information about the parsing is added

	Returns
	-------
		A list with all the OID definitions found in the simulation file
	"""

	with open(filePath, 'rb') as xmlFile:
		return ParseQADeviceSimulatorContent(xmlFile.read(), messages)

def _NormalizeValue(oidType: int, value: str) -> Optional[str]:

	"""Validate and normalize the value of a OID definition

	Returns
	-------
		The normalized value, or None if the value is not valid for the OID type
	"""

	if oidType in (OidType.OctetString.value, OidType.Opaque.value):
		return value

	if oidType == OidType.Null.value:
		return ''

	if oidType == OidType.ObjectId.value:
		value = value.strip().lstrip('.')
		return value if OID_PATTERN.match(value) else None

	if oidType == OidType.IpAddress.value:
		ipAddress = IP_ADDRESS_PATTERN.match(value.strip())
		if ipAddress and all(int(octet) <= 255 for octet in ipAddress.groups()):
			return value.strip()

		# The IP address can also be defined as 4 bytes
		if len(value) == 4 and all(ord(character) <= 0xFF for character in value):
			return value

		return None

	value = value.strip()

	if oidType == OidType.Integer32.value:
		return value if SIGNED_INTEGER_PATTERN.match(value) else None

	# Counter32, Gauge32, TimeTicks and Counter64
	return value if UNSIGNED_INTEGER_PATTERN.match(value) else None

def ConvertSimulationFile(listQADeviceSimulatorDefinition: List[QADeviceSimulatorDefinition], messages: Optional[list] = None) -> List[SnmpsimRecord]:

	"""Convert a simulation took using the QA Device Simulator to a simulation that can be used by the SNMPSIM tool.
	Definitions with an unsupported type or with an invalid OID/value are skipped (see messages).
	The records are sorted by OID and duplicated OIDs are removed (the first definition is kept)

	Arguments
	---------
		listQADeviceSimulatorDefinition: list
			A list of QADeviceSimulatorDefinition objects
		messages: list
			Optional list where information about the skipped definitions is added

	Returns
	-------
		A list containing SnmpsimRecord objects
	"""

	if messages is None:
		messages = []

	# Define an empty list with simulation records
	snmpsimRecords = []

	# Number of definitions per unsupported OID type
	unsupportedTypes = {}

	for simulationRecord in listQADeviceSimulatorDefinition:

		oid = simulationRecord.oid.strip().lstrip('.')

		if not OID_PATTERN.match(oid):
			messages.append("Invalid OID:{}, definition skipped".format(simulationRecord.oid))
			continue

		if not enumContainsName(OidType, simulationRecord.type):
			unsupportedTypes[simulationRecord.type] = unsupportedTypes.get(simulationRecord.type, 0) + 1
			continue

		oidType = OidType[simulationRecord.type].value
		value = _NormalizeValue(oidType, simulationRecord.returnValue)

		if value is None:
			messages.append("Invalid {} value for OID:{}:{!r}, definition skipped".format(simulationRecord.type, oid, simulationRecord.returnValue))
			continue

		snmpsimRecords.append(SnmpsimRecord(oid = oid, oidType = oidType, value = value))

	if unsupportedTypes:
		messages.append("{} definition(s) skipped, OID type not supported: {}".format(
			sum(unsupportedTypes.values()),
			', '.join('{} ({})'.format(oidType or '<empty>', count) for oidType, count in sorted(unsupportedTypes.items()))))

	# SNMPSIM requires the records to be sorted by OID to answer GETNEXT/GETBULK requests (e.g. SNMP walks)
	snmpsimRecords.sort(key=lambda record: tuple(int(part) for part in record.oid.split('.')))

	uniqueRecords = []
	previousOid = None

	for snmpsimRecord in snmpsimRecords:
		if snmpsimRecord.oid == previousOid:
			messages.append("Duplicated OID:{}, only the first definition is kept".format(snmpsimRecord.oid))
			continue

		previousOid = snmpsimRecord.oid
		uniqueRecords.append(snmpsimRecord)

	return uniqueRecords

def _IsPrintableAscii(value: str) -> bool:
	return all(' ' <= character <= '~' for character in value)

def _ToHex(value: str) -> str:
	encoding = 'latin-1' if all(ord(character) <= 0xFF for character in value) else 'utf-8'
	return value.encode(encoding).hex()

def FormatSnmprecRecord(snmpsimRecord: SnmpsimRecord) -> str:

	"""Format a record as a snmprec line (OID|tag|value), without line break.
	Values that cannot be written as plain text (control or non-ASCII characters, trailing whitespace, IP address
	defined as bytes) are written in hexadecimal using the tag suffix 'x' (e.g. 1.3.6.1.2.1.2.2.1.6.1|4x|000000000014)

	Arguments
	---------
		snmpsimRecord: SnmpsimRecord
			The record to format
	"""

	oid = snmpsimRecord.oid
	oidType = snmpsimRecord.oidType
	value = snmpsimRecord.value

	if oidType in (OidType.OctetString.value, OidType.Opaque.value) and not (_IsPrintableAscii(value) and value == value.rstrip()):
		return '{}|{}x|{}'.format(oid, oidType, _ToHex(value))

	if oidType == OidType.IpAddress.value and not IP_ADDRESS_PATTERN.match(value):
		return '{}|{}x|{}'.format(oid, oidType, _ToHex(value))

	return '{}|{}|{}'.format(oid, oidType, value)

def FormatSnmprecFile(listSnmpsimRecords: List[SnmpsimRecord]) -> str:

	"""Format the content of a snmprec file

	Arguments
	---------
		listSnmpsimRecords: list
			A list that contains objects of type SnmpsimRecord
	"""

	return ''.join(FormatSnmprecRecord(snmpsimRecord) + '\n' for snmpsimRecord in listSnmpsimRecords)

def GenerateSnmprecFile(listSnmpsimRecords: List[SnmpsimRecord], outputPath: str):

	"""Generate a snmprec file based on the content of the list passed as argument.
		This list will contain objects of type SnmpsimRecord

		Arguments
		---------
			listSnmpsimRecords: SnmpsimRecord
				A list that contains objects of type SnmpsimRecord
			outputPath: str
				The output path of the file to be generated
	"""

	# Check if output path is not empty
	if not outputPath:
		raise EmptyStringException("Output file path is an empty string")

	# Check if the list passed as argument is empty
	if not listSnmpsimRecords:
		raise EmptyListException("List passed as argument is empty")

	with open(outputPath, 'w', encoding='utf-8', newline='') as snmprecFile:
		snmprecFile.write(FormatSnmprecFile(listSnmpsimRecords))

@dataclass
class QAConversionResult:
	"""
	Result of converting a simulation file generated by the QA Device Simulator

	Attributes
	----------
		content: str
			The content of the snmprec file
		recordCount: int
			The number of records in the snmprec file
		messages: list
			Information about the conversion (e.g. skipped definitions)
	"""
	content: str
	recordCount: int
	messages: List[str] = field(default_factory=list)

def ConvertQADeviceSimulatorContent(data: bytes, messages: Optional[list] = None) -> QAConversionResult:

	"""Convert the content of a simulation file generated by the QA Device Simulator to the content of a snmprec file

	Arguments
	---------
		data: bytes
			The content of the simulation file (XML)
		messages: list
			Optional list where information about the conversion is added. It is also available in the result

	Returns
	-------
		A QAConversionResult with the content of the snmprec file
	"""

	if messages is None:
		messages = []

	qaDeviceSimulatorDefinitions = ParseQADeviceSimulatorContent(data, messages)

	if not qaDeviceSimulatorDefinitions:
		raise ConversionError("No OID definitions found in the simulation file")

	snmpsimRecords = ConvertSimulationFile(qaDeviceSimulatorDefinitions, messages)

	if not snmpsimRecords:
		raise ConversionError("None of the OID definitions could be converted")

	return QAConversionResult(content = FormatSnmprecFile(snmpsimRecords), recordCount = len(snmpsimRecords), messages = messages)

def ValidateFile(filePath: str) -> bool:
	"""Validate if a file exists

	Arguments
	---------
		filePath: str
			The file path of the file

	Returns
	-------
		bool
			True if the file exists. False otherwise
	"""

	return os.path.isfile(filePath)


# Main function
def main(argv: Optional[List[str]] = None) -> int:

	# Get arguments from user
	argumentParser = ArgumentParser(description='This script helps you to convert a simulation file took using the QA Device Simulator (XML file) to a file that can be used by SNMPSIM (snmprec file)')

	# Prepare the options
	argumentParser.add_argument('-i', '--input', dest='inputPath', required=True, help='File path of the simulation took using QA Device Simulator')
	argumentParser.add_argument('-o', '--output', dest='outputPath', required=True, help='File path of the snmprec file to be generated')

	# Process arguments
	arguments = argumentParser.parse_args(argv)

	# Validate the file
	if not ValidateFile(arguments.inputPath):
		print("[ERROR]|Main|File:{} could not be found".format(arguments.inputPath), file=sys.stderr)
		return 1

	print("[INFO]|Main|File:{} exists".format(arguments.inputPath), flush=True)

	messages = []

	try:
		with open(arguments.inputPath, 'rb') as inputFile:
			result = ConvertQADeviceSimulatorContent(inputFile.read(), messages)

		with open(arguments.outputPath, 'w', encoding='utf-8', newline='') as snmprecFile:
			snmprecFile.write(result.content)

	except (OSError, ConversionError) as exception:
		for message in messages:
			print("[INFO]|Main|{}".format(message))
		sys.stdout.flush()
		print("[ERROR]|Main|{}".format(exception), file=sys.stderr)
		return 1

	for message in messages:
		print("[INFO]|Main|{}".format(message))

	print("[INFO]|Main|File {} generated successfully ({} records)".format(arguments.outputPath, result.recordCount))
	return 0


if __name__ == "__main__":
	# Call the main function
	sys.exit(main())
