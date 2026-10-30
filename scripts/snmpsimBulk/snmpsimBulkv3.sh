#!/bin/bash

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Author: Miguel Obregon
# Version: 1.1
#
# Purpose: This script executes snmpsim instances (SNMPv3) based on the list of IP addresses available in the file passed as argument
#
# How to use:
# script_name.sh [options] fileName initialTransportOffset
# fileName: Name of the file that contains the list of IP addresses that will be used by snmpsim as endpoint
#           (one IP address or IP address:port per line, empty lines and lines starting with # are ignored)
# initialTransportOffset: Initial transport offset. For each IP address available in the file, the transport offset will be incremented by one
#
# Options (the default values are the values used by version 1.0):
# -d|--data-dir <folder>       SNMP data directory (default: /home/skyline/.local/snmpsim/data/public)
# -u|--process-user <user>     User used by snmpsim when the script is executed as root (default: skyline)
# -g|--process-group <group>   Group used by snmpsim when the script is executed as root (default: skyline)
# -L|--log-dir <folder>        Folder with one log file per snmpsim instance (default: /tmp/snmpsimBulk)
# -c|--command <path>          Path of the snmpsim command responder (default: found in the activated virtual
#                              environment, in the PATH or in /home/<process user>/.local/bin)
# --v3-user <user>             SNMPv3 user (default: skyline)
# --v3-auth-key <key>          SNMPv3 authentication key (default: Skyline321)
# --v3-auth-proto <protocol>   SNMPv3 authentication protocol, e.g. MD5, SHA (default: MD5)
# --v3-priv-key <key>          SNMPv3 privacy key (default: Skyline321)
# --v3-priv-proto <protocol>   SNMPv3 privacy protocol, e.g. DES, AES (default: DES)
#
# Example:
# snmpsimBulkv3.sh ipAddresses.txt 1
#
# Version history:
# 1.0: Initial version
# 1.1: Use snmpsim-command-responder (snmpsimd.py is not available in snmpsim 1.x), options for the hard-coded values,
#      SNMPv3 keys are no longer printed, one log file per instance, support files with CRLF line endings, empty lines,
#      comments or without a final new line
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Retrieve the name of script
scriptName=$(basename "$0")

# SNMPv3 user
snmpv3User="skyline"

# SNMPv3 Authentication Key Password and protocol
snmpv3AuthPassword="Skyline321"
snmpv3AuthProtocol="MD5"

# SNMPv3 Private Key Password and protocol
snmpv3PrivPassword="Skyline321"
snmpv3PrivProtocol="DES"

# SNMP Data directory
snmpDataDirectory="/home/skyline/.local/snmpsim/data/public"

# User and group used by snmpsim when the script is executed as root (required to use the default SNMP port 161)
processUser="skyline"
processGroup="skyline"

# Folder with the log files of the snmpsim instances
logDirectory="${TMPDIR:-/tmp}/snmpsimBulk"

# SNMPSIM command responder
snmpsimCommand="snmpsim-command-responder"
snmpsimPath=""

function usage() {
	cat << EOF
Usage: $scriptName [options] fileName initialTransportOffset
Options:
  -d|--data-dir <folder>       SNMP data directory (default: $snmpDataDirectory)
  -u|--process-user <user>     User used by snmpsim when the script is executed as root (default: $processUser)
  -g|--process-group <group>   Group used by snmpsim when the script is executed as root (default: $processGroup)
  -L|--log-dir <folder>        Folder with one log file per snmpsim instance (default: $logDirectory)
  -c|--command <path>          Path of the snmpsim command responder
  --v3-user <user>             SNMPv3 user (default: $snmpv3User)
  --v3-auth-key <key>          SNMPv3 authentication key
  --v3-auth-proto <protocol>   SNMPv3 authentication protocol, e.g. MD5, SHA (default: $snmpv3AuthProtocol)
  --v3-priv-key <key>          SNMPv3 privacy key
  --v3-priv-proto <protocol>   SNMPv3 privacy protocol, e.g. DES, AES (default: $snmpv3PrivProtocol)
EOF
}

# Check that an option has a value
function requireValue() {
	if [[ -z "${2-}" || "${2:0:1}" == "-" ]]; then
		echo "[ERROR]|Main|Option $1 requires a value" >&2
		exit 2
	fi
}

# Process the options
arguments=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		-d|--data-dir) requireValue "$1" "${2-}"; snmpDataDirectory=$2; shift 2 ;;
		-u|--process-user) requireValue "$1" "${2-}"; processUser=$2; shift 2 ;;
		-g|--process-group) requireValue "$1" "${2-}"; processGroup=$2; shift 2 ;;
		-L|--log-dir) requireValue "$1" "${2-}"; logDirectory=$2; shift 2 ;;
		-c|--command) requireValue "$1" "${2-}"; snmpsimPath=$2; shift 2 ;;
		--v3-user) requireValue "$1" "${2-}"; snmpv3User=$2; shift 2 ;;
		--v3-auth-key) requireValue "$1" "${2-}"; snmpv3AuthPassword=$2; shift 2 ;;
		--v3-auth-proto) requireValue "$1" "${2-}"; snmpv3AuthProtocol=$2; shift 2 ;;
		--v3-priv-key) requireValue "$1" "${2-}"; snmpv3PrivPassword=$2; shift 2 ;;
		--v3-priv-proto) requireValue "$1" "${2-}"; snmpv3PrivProtocol=$2; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		-*) echo "[ERROR]|Main|Unknown option: $1" >&2; usage >&2; exit 2 ;;
		*) arguments+=("$1"); shift ;;
	esac
done

# Check the number of argumented passed to the script
if [ "${#arguments[@]}" -ne 2 ]; then
	echo -e "[ERROR]|Main|This script requires two arguments:" >&2
	echo -e "$scriptName [options] fileName initialTransportOffset" >&2

	# Exit the script
	exit 2
fi

# Retrieve the file name and the initial transport offset
fileName=${arguments[0]}
initialTransportOffset=${arguments[1]}

# Check if the file exists
if [ ! -f "$fileName" ]; then
	echo "[ERROR]|Main|Source file:$fileName not available" >&2
	exit 2
fi

if ! [[ "$initialTransportOffset" =~ ^[0-9]+$ ]]; then
	echo "[ERROR]|Main|InitialTransportOffset:$initialTransportOffset is not a number" >&2
	exit 2
fi

if [ ! -d "$snmpDataDirectory" ]; then
	echo "[ERROR]|Main|SNMPSIM Data Directory:$snmpDataDirectory not available" >&2
	exit 2
fi

# Find the snmpsim command responder
if [[ -z "$snmpsimPath" ]]; then
	if [[ -n "${VIRTUAL_ENV-}" && -x "$VIRTUAL_ENV/bin/$snmpsimCommand" ]]; then
		snmpsimPath="$VIRTUAL_ENV/bin/$snmpsimCommand"
	elif command -v "$snmpsimCommand" > /dev/null 2>&1; then
		snmpsimPath=$(command -v "$snmpsimCommand")
	else
		snmpsimPath="/home/$processUser/.local/bin/$snmpsimCommand"
	fi
fi

if [[ ! -x "$snmpsimPath" ]]; then
	echo "[ERROR]|Main|SNMPSIM command:$snmpsimPath not available. Use the option --command to define its path" >&2
	exit 2
fi

# Arguments used by all the snmpsim instances
snmpsimArguments=(
	"--v3-user=$snmpv3User"
	"--v3-auth-key=$snmpv3AuthPassword"
	"--v3-auth-proto=$snmpv3AuthProtocol"
	"--v3-priv-key=$snmpv3PrivPassword"
	"--v3-priv-proto=$snmpv3PrivProtocol"
	"--data-dir=$snmpDataDirectory"
)

# snmpsim only accepts a process user and group when it is executed as root
if [[ $EUID -eq 0 ]]; then
	snmpsimArguments+=("--process-user=$processUser" "--process-group=$processGroup")
fi

mkdir -p "$logDirectory"

echo -e "+++++++++++++++++++++"
echo -e "[INFO]|Main|Arguments"
echo -e "+++++++++++++++++++++"
echo -e "[INFO]|Main|fileName:$fileName"
echo -e "[INFO]|Main|InitialTransportOffset:$initialTransportOffset"
echo -e "+++++++++++++++++++++++++++++++++"
echo -e "[INFO]|Main|SNMPSIM Configuration"
echo -e "+++++++++++++++++++++++++++++++++"
echo -e "[INFO]|Main|SNMPv3 User:$snmpv3User"
echo -e "[INFO]|Main|SNMPv3 Authentication Protocol:$snmpv3AuthProtocol"
echo -e "[INFO]|Main|SNMPv3 Privacy Protocol:$snmpv3PrivProtocol"
echo -e "[INFO]|Main|SNMPSIM Path:$snmpsimPath"
echo -e "[INFO]|Main|SNMPSIM Data Directory:$snmpDataDirectory"
echo -e "[INFO]|Main|SNMPSIM Log Directory:$logDirectory"

# Define a counter of lines
lineNumber=0
instanceCount=0
pids=()
logFiles=()

# Read the content of the file. The last line is also processed when it does not end with a new line
while IFS= read -r line || [[ -n "$line" ]]; do
	lineNumber=$((lineNumber + 1))

	# Remove the carriage returns (CRLF line endings) and the whitespaces
	line=${line//$'\r'/}
	line=${line//[[:space:]]/}

	# Skip empty lines and comments
	if [[ -z "$line" || "$line" == \#* ]]; then
		continue
	fi

	# Reading each line (that contains the IP address)
	echo "[INFO]|Main|$lineNumber: IP Address= $line"

	# Define the offset
	offset=$((initialTransportOffset + instanceCount))

	logFile="$logDirectory/${line//[^A-Za-z0-9._-]/_}.log"

	# Execute the SNMPSIM command
	"$snmpsimPath" \
		--agent-udpv4-endpoint="$line" \
		--transport-id-offset="$offset" \
		"${snmpsimArguments[@]}" \
		> "$logFile" 2>&1 &

	pids+=("$!")
	logFiles+=("$logFile")
	instanceCount=$((instanceCount + 1))
done < "$fileName"

if [[ $instanceCount -eq 0 ]]; then
	echo "[ERROR]|Main|No IP addresses found in the file:$fileName" >&2
	exit 2
fi

# Check that the instances are still running after their start up
sleep 3
failedCount=0
for index in "${!pids[@]}"; do
	if kill -0 "${pids[$index]}" 2> /dev/null; then
		echo "[INFO]|Main|PID ${pids[$index]} running (log: ${logFiles[$index]})"
	else
		echo "[ERROR]|Main|PID ${pids[$index]} stopped. Check the log file: ${logFiles[$index]}" >&2
		failedCount=$((failedCount + 1))
	fi
done

if [[ $failedCount -gt 0 ]]; then
	exit 1
fi
