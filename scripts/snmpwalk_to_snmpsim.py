"""
The purpose of this script is to format a SNMP walk took by Net-SNMP Tools
The following errors are detected:
- SNMP walk that contains invalid characters (e.g non-printable characters). These invalid characters are removed from the SNMP walk record
- Start of a line does not start with ".1.3.6" or "1.3.6". The script will append this line with the previous record (that starts with ".1.3.6" or "1.3.6")

Encoding part was retrieved from: https://stackoverflow.com/questions/191359/how-to-convert-a-file-to-utf-8-in-python
"""

__version__ = '1.0'
__author__ = 'Miguel Obregon'

import codecs
import linecache
from pickletools import float8
import sys
import argparse		# Argument parser used to pass arguments to the scripts
import re			# Regular Expressions
import getopt		# Arguments in command line
import os.path		# Library used to read/write files
import codecs		# Process file encoding
from chardet import detect

# Constants
targetFormat = 'utf-8'

# Object initialization for the decoding
#detector = UniversalDetector()

def matchInvalidStartNewline(sLine):
	"""
	Matches an invalid new line (the start of the new line)

	Parameters
	----------
	sLine: str
		Line to be validated

	Returns
	-------
		A boolean indicating if the line is invalid
	"""

	# Define the matching pattern
	pattern = '^[A-F9-f0-9]{2}\s*'
	return (re.search(pattern,sLine))

def getEncodingType(sourceFile:str):
	"""
	Get the encoding type of the file passed as argument

	Parameters
	----------
	sourceFile: str
		File to be checked
	"""
	with open(sourceFile, 'rb') as file:
		rawdata = file.read()
	
	return detect(rawdata)['encoding']

def convertFileBestGuess(inputFilePath:str, outputFilePath:str):
	"""
	Tries to detect the encoding in a file based on the predefined list (defined in sourceFormats), and if it is found, it will convert the file to the pre-defined encoding
	The pre-defined encoding is available is defined in the method writeConversion

	Parameters
	----------
	filePath: str
		File path of the file to be converted
	"""
	sourceFormats = ['ascii', 'iso-8859-1']
	for format in sourceFormats:
		try:
			with codecs.open(filename=inputFilePath, mode='rU', encoding=format) as sourceFile:
				writeConversion(sourcefilePath=sourceFile,outputFilePath=outputFilePath)
				print('[INFO]|convertFileBestGuess|Conversion done')
		except UnicodeDecodeError:
			pass

def convertFileWithDetection(inputFilePath:str, outputFilePath:str):
	"""
	Tries to detect the encoding in a file, and if it is found, it will convert the file to the pre-defined encoding
	The pre-defined encoding is available is defined in the method writeConversion

	Parameters
	----------
	inputFilePath: str
		File path of the file to be converted
	outputFilePath: str
		File path of the converted file
	"""
	print('[INFO]|convertFileWithDetection|Converting file:{}'.format(inputFilePath))

	# Get the encoding type of the file
	format = getEncodingType(inputFilePath)

	try:
		with codecs.open(filename=inputFilePath, mode='rU', encoding=format) as sourceFile:
			# If the encoding was found, it will convert the file to the pre-defined encoding type
			writeConversion(sourcefilePath=sourceFile, outputFilePath=outputFilePath)

			print('[INFO]|convertFileWithDetection|Conversion done')
			return
	except UnicodeDecodeError:
		pass
	print('[ERROR]|convertFileWithDetection|Failed to convert file:{}'.format(inputFilePath))

def writeConversion(sourcefilePath:str, outputFilePath:str):
	"""
	Converts a file to the encoding defined in the variable targetFormat (utf-8)

	Parameters
	----------
	sourceFilePath: str
		File path of the file to be converted
	outputFilePath: str
		File path of the converted file
	"""
	with codecs.open(filename=outputFilePath, mode='w', encoding=targetFormat) as targetFile:
		for line in sourcefilePath:
			targetFile.write(line)

def main():

	# Create the parser object
	parser = argparse.ArgumentParser(description='Read a SNMP walk and detect possible issues that avoids the conversion to snmprec files')

	# Define the arguments
	parser.add_argument('-i', '--input', dest='inputFile', help='File Path of the SNMP walk', type=str)
	parser.add_argument('-o', '--output', dest='outputFile', help='File Path of the SNMP walk converted', type=str)

	# Check if no arguments were provided
	if len(sys.argv) == 1:
		# If no argument were provided, show help message
		parser.print_help(sys.stderr)
		sys.exit(1)

	# Process arguments
	arguments = parser.parse_args()

	# Variables that stores the arguments from the command line
	inputFile = arguments.inputFile
	outputFile = arguments.outputFile

	# Load all lines in an list
	saTextFile = []
	lineCount = 0

	# Temporary File
	temporaryFilePath = inputFile + '_temp'

	# First we will change the encoding type
	convertFileWithDetection(inputFilePath=inputFile, outputFilePath=temporaryFilePath)

	# Opening a text file content (r - Read) and store the content in a list
	with open(file=temporaryFilePath, mode='r', encoding=targetFormat, errors="ignore") as inTextFile, open(file=outputFile, mode='w', encoding=targetFormat) as outTextFile:
	#with open(inputFile, 'r') as inTextFile, open(outputFile, mode='w') as outTextFile:

		# Define a parameter that will hold the previous line
		previousLine = ''

		for line in inTextFile:

			# Line counter
			lineCount += 1

			# Escape characters
			# \f: Form feed (in vim: ^M)
			# \v: Vertical block (in vim: ^V)
			# \t: Tab (in vim: -->)
			lineUpdated = re.sub(r"[\n\t\f\v]*", "", line)

			#if(not lineWithoutTabCharacter.isprintable()):
			if(not lineUpdated.isprintable()):
				
				# We have an invalid character that has to be checked
				print('[INFO]|Main|Line[{}]: This line contains an invalid character'.format(lineCount))

			else:

				# Remove the leading and trailing whitespaces
				#lineUpdated = lineUpdated.strip()

				# We start parsing lines with valid characters
				# Check first if the line start with ".1.3.6" (valid SNMP walk record)
				if (not (lineUpdated.startswith(".1.3.6.") or lineUpdated.startswith("1.3.6."))):

					# Process invalid SNMP walk records
					print("[INFO]|Main|Line[{}]: Not valid SNMP walk record:{}".format(lineCount, lineUpdated))

					lineUpdated = previousLine + lineUpdated
					previousLine = lineUpdated

				if (lineUpdated.find("TenthdBmV") != -1 or lineUpdated.find("TenthdB") != -1):

					# Process invalid SNMP walk record that contains the unit TenthdBmV (assuming that this record is a INTEGER type)
					
					# Get the substring after 'INTEGER'
					linePartitioned = lineUpdated.partition("INTEGER:")

					# Get the value without the units (convert to float since the value will contain a decimal part)
					rawValue = float(re.sub('[^-?\d+\.]', "", linePartitioned[2]))

					lineUpdated = linePartitioned[0] + linePartitioned[1] + ' ' + str(int(rawValue * 10))

					#print("[INFO]|Main|Line Updated:{}".format(linePartitioned[0] + linePartitioned[1] + ' ' + str(int(rawValue * 10))))

					outTextFile.write("{}\n".format(lineUpdated))
					previousLine = lineUpdated
				else:
					# Checking a special case when the snmpwalk returns a 'No Such Object available'
					if (lineUpdated.find("No Such Object available on this agent at this OID") != -1):

						# When converting from snmpwalk to snmprec, we noticed that this entry is causing issues, so we proceed to not add it to the output
						print("[INFO]|Main|Line[{}]: Invalid SNMP record: No Such Object available on this agent at this OID".format(lineCount))
						continue
					else:
						outTextFile.write("{}\n".format(previousLine))
						previousLine = lineUpdated

	# Finally, remove the temporary file
	if os.path.exists(temporaryFilePath):
		os.remove(path=temporaryFilePath)
		print('[INFO]|Main|Temporary file removed')
	else:
		print('[INFO]|Main|Temporary file:{} could not be found'.format(temporaryFilePath))

if __name__ == "__main__":
	sys.exit(main())