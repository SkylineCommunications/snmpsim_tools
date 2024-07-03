#!/usr/bin/env python

"""qa_device_simulator_to_snmpsim.py: Convert simulations took from QA Device Simulator (XML file extension) to snmpsim simulations (snmprec extension)"""

__author__		= "Miguel Obregon"
__copyright__	= "Skyline Communications"
__version__		= "1.0.1"
__status__		= "Development"

# Modules
from email.errors import MalformedHeaderDefect
import xml.etree.ElementTree # Module used to parse XML files
import csv # Module used to generate parse and generate CSV files
import os	# Module used to work with OS files and directories
import sys # Module used to work with running application
from argparse import ArgumentParser # Module used to parse arguments
from enum import Enum # Module used to define enumerations
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


# +++++++
# Methods
# +++++++

def ParseQADeviceSimulatorFile(filePath: str):

	"""Parse the HTTP response for the endpoint /snmpset and perform a SNMP set based on the information available in the body of the response

	Parameters
	----------
		filePath: str

	Returns
	-------
		A list with all the OID definitions found in the simulation file
	"""

	try:

		# Create element tree object
		treeObject = xml.etree.ElementTree.parse(filePath)

		# Get the root element
		rootElement = treeObject.getroot()

		# Create an empty list with simulation records
		qaDeviceSimulatorDefinitions = []

		# We noticed that depending of the age of simulation, a different XML structure is used.
		# We will make this distinction based on the amount of OID definitions
		if (len(rootElement.findall('.Definitions/Definition')) == 0):
			print("[INFO]|ParseQADeviceSimulatorFile|OID definitions not found, we will try to get the definition from an old structure")

			if (len(rootElement.findall('.Definition')) == 0):
				print("[INFO]|ParseQADeviceSimulatorFile|No OID definitions found")
				return qaDeviceSimulatorDefinitions
			else:
				print("[INFO]|ParseQADeviceSimulatorFile|Number of OID definitions: {}".format(len(rootElement.findall('.Definition'))))
				listDefinitions = rootElement.findall('.Definition')
		else:
			print("[INFO]|ParseQADeviceSimulatorFile|Number of OID definitions: {}".format(len(rootElement.findall('.Definitions/Definition'))))
			listDefinitions = rootElement.findall('.Definitions/Definition')

		# Iterate through the simulation records
		for simulationRecord in listDefinitions:

			#print("[INFO]|ParseQADeviceSimulatorFile|oid:{}".format(simulationRecord.attrib['OID']))
			#print("[INFO]|ParseQADeviceSimulatorFile|oidType:{}".format(simulationRecord.attrib['Type']))

			qaDeviceSimulatorDefinition = QADeviceSimulatorDefinition(

				oid = simulationRecord.attrib['OID'],
				type = simulationRecord.attrib['Type'],
				returnValue = simulationRecord.attrib['ReturnValue'],
				logOutput = simulationRecord.attrib ['LogOutput'] if hasattr(simulationRecord, 'LogOutput') else None,
				comment = simulationRecord.attrib['Comment'] if hasattr(simulationRecord, 'Comment') else None,
				# Added these extra checks since old simulations don't contain these attributes
				delay = simulationRecord.attrib['Delay'] if hasattr(simulationRecord, 'Delay') else None,
				save = simulationRecord.attrib['Save'] if hasattr(simulationRecord, 'Save') else None,
				skipOid = simulationRecord.attrib['SkipOID'] if hasattr(simulationRecord, 'SkipOID') else None
				)

			#print("[INFO]|ParseQADeviceSimulatorFile|oid:{}".format(qaDeviceSimulatorDefinition.oid))
			#print("[INFO]|ParseQADeviceSimulatorFile|oidType:{}".format(qaDeviceSimulatorDefinition.type))

			qaDeviceSimulatorDefinitions.append(qaDeviceSimulatorDefinition)

		return qaDeviceSimulatorDefinitions

	except Exception as exception:
		print("[ERROR]|ParseQADeviceSimulatorFile|Exception:{}".format(str(exception)))

def ConvertSimulationFile(listQADeviceSimulatorDefinition: QADeviceSimulatorDefinition):

	"""Convert a simulation took using the QA Device Simulator to a simulation that can be used by the SNMPSIM tool

	Arguments
	---------
		listQADeviceSimulatorDefinition: QADeviceSimulatorDefinition
			A list of QADeviceSimulatorDefinition objects

	Returns
	-------
		A list containing SnmpsimRecord objects
	"""

	try:
		# Define an empty list with simulation records
		snmpsimRecords = []

		for simulationRecord in listQADeviceSimulatorDefinition:

			if(enumContainsName(OidType, simulationRecord.type)):

				snmpsimRecord = SnmpsimRecord(
					oid = simulationRecord.oid,
					oidType = OidType[simulationRecord.type].value,
					value = simulationRecord.returnValue
				)

				# print("[INFO]|ConvertSimulationFile|snmpsimRecord.oid:{}".format(snmpsimRecord.oid))
				# print("[INFO]|ConvertSimulationFile|snmpsimRecord.oidType:{}".format(snmpsimRecord.oidType))
				# print("[INFO]|ConvertSimulationFile|snmpsimRecord.value:{}".format(snmpsimRecord.value))

				# Add the temporary object to the list
				snmpsimRecords.append(snmpsimRecord)
			else:
				raise Exception("[ERROR]|ConvertSimulationFile|OID type not found for simulation record:OID:{},OID Type:{}".format(simulationRecord.oid, simulationRecord.type))
				# print("[ERROR]|ConvertSimulationFile|OID type not found for simulation record:")
				# print("[ERROR]|ConvertSimulationFile|OID:{}".format(simulationRecord.oid))
				# print("[ERROR]|ConvertSimulationFile|OID:{}".format(simulationRecord.type))

		return snmpsimRecords

	except Exception as exception:
		print("[ERROR]|ConvertSimulationFile|Exception:{}".format(str(exception)))

def GenerateSnmprecFile(listSnmpsimRecords: SnmpsimRecord, outputPath: str):

	"""Generate a snmprec file based on the content of the list passed as argument.
		This list will contain objects of type SnmpsimRecord

		Arguments
		---------
			listSnmpsimRecords: SnmpsimRecord
				A list that contains objects of type SnmpsimRecord
			outputPath: str
				The output path of the file to be generated
	"""

	try:

		# Validate the arguments

		# Check if output path is not empty
		if not outputPath:
			raise EmptyListException("[ERROR]|GenerateSnmprecFile|Exception:Output file path is an empty string")

		# Check if the list passed as argument is empty
		if not listSnmpsimRecords:
			raise EmptyListException("[ERROR]|GenerateSnmprecFile|Exception:List passed as argument is empty")

		with open(outputPath, 'w', newline='') as snmprecFile:

			# Create a CSV writer object
			writer = csv.writer(snmprecFile, delimiter='|')

			for snmpsimRecord in listSnmpsimRecords:
				writer.writerow([snmpsimRecord.oid, snmpsimRecord.oidType, snmpsimRecord.value])

	except EmptyListException as exception:
		print(exception)
	except EmptyStringException as exception:
		print(exception)
	except Exception as exception:
		print("[ERROR]|GenerateSnmprecFile|Exception:{}".format(str(exception)))
	
	else:
		print("[INFO]|GenerateSnmprecFile|File {} generated successfully".format(outputPath))

def ValidateFile(filePath: str) -> bool:
	"""Validate if a file exists

	Arguments
	---------
		filePath: str
			The file path of the VSDX file

	Returns
	-------
		bool
			True if the file exists. False otherwise
	"""

	bFileExists = os.path.exists(filePath)

	if(bFileExists):
		return True
	else:
		return False

def ValidateAndReplaceXmlFile(filePath: str):
	"""Validate a XML by checking invalid characters (encoding issues)
	In case it finds invalid characters, they will be replaced by a string of zeros with a dot.
	For example '&#x00;' will be replaced with '00.'
	For example '&#x1D;' will be replaced with '00.'
	
	Arguments
	---------
		filePath: str
			The file path of the VSDX file
	
	Returns
	-------
		The file path of the updated file (with the suffix 'updated')

	"""
	if ValidateFile(filePath):

		try:
			# Define a list that will contain the lines of the updated file
			updatedLines = []

			with open(filePath,'r') as xmlFile:
				
				fileLines = xmlFile.readlines()

				for line in fileLines:

					malformedEncodingFound = re.search(r"&#x(\d{1,2});|&#x([a-zA-Z]|1[a-zA-Z]);", line)

					if (malformedEncodingFound):

						# Since we found a line with invalid characters, we proceed to replace the invalid characters
						lineReplaced = re.sub(r"&#x(\d{1,2}|[a-zA-Z]|1[a-zA-Z]);", r"0\1.", line)

						# Add the line replaced to the file
						updatedLines.append(lineReplaced)
					else:
						updatedLines.append(line)
			
			# Get the name of the file without the extension
			filePathWithoutExtension = os.path.splitext(filePath)[0]

			# Define the name of the updated file
			updatedFileName = filePathWithoutExtension + '_updated.xml'

			# Writing the new file
			with open(updatedFileName,'w') as xmlUpdatedFile:
				xmlUpdatedFile.writelines(updatedLines)

			return updatedFileName

		except Exception as exception:
			print("[ERROR]|ValidateXmlFile|Exception:{}".format(str(exception)))
	else:
		print("[ERROR]|ValidateXmlFile|XML file:{} could not be found".format(filePath))


# Main function
def main():

	try:

		# Get arguments from user
		argumentParser = ArgumentParser(description='This script helps you to convert a simulation file took using the QA Device Simulator (XML file) to a file that can be used by SNMPSIM (snmprec file)')

		# Prepare the options
		argumentParser.add_argument('-i', '--input', dest='inputPath', required=True, help='File path of the simulation took using QA Device Simulator')
		argumentParser.add_argument('-o', '--output', dest='outputPath', required=True, help='File path of the snmprec file to be generated')

		# Process arguments
		arguments = argumentParser.parse_args()

		# Validate the file
		if (ValidateFile(arguments.inputPath)):
			
			print("[INFO]|Main|File:{} exists".format(arguments.inputPath))

			# Define a empty list that will contain objects of type QADeviceSimulatorDefinition
			qaDeviceSimulatorDefinitions = []

			# Define a empty list that will contain objects of type SnmpsimRecord
			snmpsimRecords = []

			# Validate the replace. In case of incorrect characters, the file will be updated
			updatedFileName = ValidateAndReplaceXmlFile(arguments.inputPath)

			print("[INFO]|Main|Updated file created:{}".format(updatedFileName))

			# Parse the content of the simulation file that was took using the QA Device Simulator tool
			qaDeviceSimulatorDefinitions = ParseQADeviceSimulatorFile(updatedFileName)

			if not qaDeviceSimulatorDefinitions:
				raise SystemExit()
			else:
				# Convert the simulation file to a different object type
				snmpsimRecords = ConvertSimulationFile(qaDeviceSimulatorDefinitions)

			if not snmpsimRecords:
				raise SystemExit()
			else:
				# Generate the snmprec file
				GenerateSnmprecFile(snmpsimRecords, arguments.outputPath)

		else:
			print("[INFO]|Main|File could not be processed. Could you check if the file exists?")
			print("[INFO]|Main|Closing the application")

	# except SystemExit:
	# 	print("[ERROR]|GenerateSnmprecFile|Exception:{}".format(str(exception)))
	except Exception as exception:
		print("[ERROR]|Main|Exception:{}".format(str(exception)))


if __name__ == "__main__":
	# Call the main function
	main()