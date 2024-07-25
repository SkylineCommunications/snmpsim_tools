#!/bin/bash

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Author: Miguel Obregon
# Version: 1.0
#
# Purpose: This script executes snmpsim instances based on the list of IP addresses available in the file passed as argument
#
# How to use:
# script_name.sh fileName initialTransportOffset
# fileName: Name of the file that contains the list of IP addresses that will be used by snmpsim as endpoint
# initialTransportOffset: Initial transport offset. For each IP address available in the file, the transport offset will be incremented by one
#
# Example:
# snmpsimBulk fileName
#
# Version history:
# 1.0: Initial version
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Variables
CURRENT_DIRECTORY="$PWD"

# Retrieve the name of script
scriptName=`basename "$0"`

# Retrieve the file name
fileName=$1

# Retrieve the initial transport offset
initialTransportOffset=$2

# SNMPSIM application path
snmpsimPath="/home/skyline/.local/bin/snmpsimd.py "

# SNMP Data directory
snmpDataDirectory="/home/skyline/.local/snmpsim/data/public"

# Check the number of argumented passed to the script
if [ "$#" -ne 2 ]; then
	
	echo -e "[ERROR]|Main|This script requires two arguments:\r"
	echo -e "$scriptName fileName initialTransportOffset"
	
	# Exit the script
	exit 2
fi

# Check if the file exists
if [ ! -f "$1" ]; then
	# The file does not exist
	echo "[ERROR]|Main|Source file:$1 not available\r"
	exit 2
else
	# Define a counter of lines
	lineNumber=1
	
	echo -e "+++++++++++++++++++++"
	echo -e "[INFO]|Main|Arguments"
	echo -e "+++++++++++++++++++++"
	echo -e "[INFO]|Main|fileName:$1"
	echo -e "[INFO]|Main|InitialTransportOffset:$2"
	echo -e "+++++++++++++++++++++++++++++++++"
	echo -e "[INFO]|Main|SNMPSIM Configuration"
	echo -e "+++++++++++++++++++++++++++++++++"
	echo -e "[INFO]|Main|SNMPSIM Path:$snmpsimPath"
	echo -e "[INFO]|Main|SNMPSIM Data Directory:$snmpDataDirectory"

	# Read the content of the file
	while read line;
	do
		# Reading each line (that contains the IP address)
		echo "[INFO]|Main|$lineNumber: IP Address= $line"
		
		# Split the IP address into octets
		IFS='.' read -ra octetsIpAddress <<< "$line"

		# Define the offset
		offset=$(($lineNumber + $initialTransportOffset - 1))

		# Execute the SNMPSIM command
		python $snmpsimPath \
		--agent-udpv4-endpoint=$line \
		--data-dir=$snmpDataDirectory \
		--transport-id-offset=$offset \
		--v2c-arch \
		--process-user=skyline \
		--process-group=skyline \
		> /dev/null 2>/dev/null &

		# Increment the line counter
		lineNumber=$((lineNumber+1))
	done < $fileName
fi