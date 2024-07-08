#!/usr/bin/env bash

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Purpose: This script executes a single snmpsim instance. For this case the following arguments are required
# - snmprecFolder: The folder that contains the simulation file to be used by snmpsim
# - ipAddress: The IP address of the simulated SNMP agent
# - port: The port port of the simulated SNMP agent
#
# The main purpose of this bash script is to avoid the length command line options of snmpsim
#
# How to use:
# script_name.sh --snmprecFolder /home/myUser/mySnmprecFolder --ipAddress 10.11.12.13 --port 10161
# script_name.sh -f /home/myUser/mySnmprecFolder -i 10.11.12.13 -p 10161
#
# Arguments:
# f|snmprecFolder: The folder that contains the simulation file (full path)
# i|ipAddress: The IP address of the simulated SNMP agent
# p|Port: The port port of the simulated SNMP agent
#
# Version history:
# 1.0.1, Miguel Obregon, Initial version
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Global variables

# SNMPSIM application path
#snmpsimPath="/home/$USER/.local/bin/snmpsimd.py"
snmpsimPath="/home/$USER/.local/bin/snmpsim-command-responder-lite"

# SNMPSIM Variation module folder path
# Since this path depends of the python minor version (3.10.1 -> 10 is the minor version) we move this variable to main method
#snmpsimVariationModulePath="/home/$USER/.local/snmpsim/variation"
#snmpsimVariationModulePath="home/$USER/.local/lib/python3.10/site-packages/snmpsim/variation"

# SNMPSIM PID file
snmpsimPidFilePath="/home/$USER/Documents/snmpsim/debug/daemon/daemon"

# SNMPSIM Log folder
snmmpsimLogFolder="/home/$USER/Documents/snmpsim/debug/logging/"

# SNMPSIM Report folder
snmpsimReportFolder="/home/$USER/Documents/snmpsim/debug/reports/"

# Bash script template used: https://github.com/ralish/bash-script-template

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# START: Helper functions (not to be modified)
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# A best practices Bash script template with many useful functions. This file
# sources in the bulk of the functions from the source.sh file which it expects
# to be in the same directory. Only those functions which are likely to need
# modification are present in this file. This is a great combination if you're
# writing several scripts! By pulling in the common functions you'll minimise
# code duplication, as well as ease any potential updates to shared functions.

# Enable xtrace if the DEBUG environment variable is set
if [[ ${DEBUG-} =~ ^1|yes|true$ ]]; then
	set -o xtrace		# Trace the execution of the script (debug)
fi

# Only enable these shell behaviours if we're not being sourced
# Approach via: https://stackoverflow.com/a/28776166/8787985
if ! (return 0 2> /dev/null); then
	# A better class of script...
	set -o errexit		# Exit on most errors (see the manual)
	set -o nounset		# Disallow expansion of unset variables
	set -o pipefail		# Use last non-zero exit code in a pipeline
fi

# Enable errtrace or the error trap handler will not work as expected
set -o errtrace			# Ensure the error trap handler is inherited

# DESC: Handler for unexpected errors
# ARGS: $1 (optional): Exit code (defaults to 1)
# OUTS: None
function script_trap_err() {
	local exit_code=1

	# Disable the error trap handler to prevent potential recursion
	trap - ERR

	# Consider any further errors non-fatal to ensure we run to completion
	set +o errexit
	set +o pipefail

	# Validate any provided exit code
	if [[ ${1-} =~ ^[0-9]+$ ]]; then
		exit_code="$1"
	fi

	# Output debug data if in Cron mode
	if [[ -n ${cron-} ]]; then
		# Restore original file output descriptors
		if [[ -n ${script_output-} ]]; then
			exec 1>&3 2>&4
		fi

		# Print basic debugging information
		printf '%b\n' "$ta_none"
		printf '***** Abnormal termination of script *****\n'
		printf 'Script Path:            %s\n' "$script_path"
		printf 'Script Parameters:      %s\n' "$script_params"
		printf 'Script Exit Code:       %s\n' "$exit_code"

		# Print the script log if we have it. It's possible we may not if we
		# failed before we even called cron_init(). This can happen if bad
		# parameters were passed to the script so we bailed out very early.
		if [[ -n ${script_output-} ]]; then
			# shellcheck disable=SC2312
			printf 'Script Output:\n\n%s' "$(cat "$script_output")"
		else
			printf 'Script Output:          None (failed before log init)\n'
		fi
	fi

	# Exit with failure status
	exit "$exit_code"
}

# DESC: Handler for exiting the script
# ARGS: None
# OUTS: None
function script_trap_exit() {
	cd "$orig_cwd"

	# Remove Cron mode script log
	if [[ -n ${cron-} && -f ${script_output-} ]]; then
		rm "$script_output"
	fi

	# Remove script execution lock
	if [[ -d ${script_lock-} ]]; then
		rmdir "$script_lock"
	fi

	# Restore terminal colours
	printf '%b' "$ta_none"
}

# DESC: Exit script with the given message
# ARGS: $1 (required): Message to print on exit
#       $2 (optional): Exit code (defaults to 0)
# OUTS: None
# NOTE: The convention used in this script for exit codes is:
#       0: Normal exit
#       1: Abnormal exit due to external error
#       2: Abnormal exit due to script error
function script_exit() {
	if [[ $# -eq 1 ]]; then
		printf '%s\n' "$1"
		exit 0
	fi

	if [[ ${2-} =~ ^[0-9]+$ ]]; then
		printf '%b\n' "$1"
		# If we've been provided a non-zero exit code run the error trap
		if [[ $2 -ne 0 ]]; then
			script_trap_err "$2"
		else
			exit 0
		fi
	fi

	script_exit '[ERROR]|Missing required argument to script_exit()!' 2
}

# DESC: Generic script initialisation
# ARGS: $@ (optional): Arguments provided to the script
# OUTS: $orig_cwd: The current working directory when the script was run
#       $script_path: The full path to the script
#       $script_dir: The directory path of the script
#       $script_name: The file name of the script
#       $script_params: The original parameters provided to the script
#       $ta_none: The ANSI control code to reset all text attributes
# NOTE: $script_path only contains the path that was used to call the script
#       and will not resolve any symlinks which may be present in the path.
#       You can use a tool like realpath to obtain the "true" path. The same
#       caveat applies to both the $script_dir and $script_name variables.
# shellcheck disable=SC2034
function script_init() {
	# Useful variables
	readonly orig_cwd="$PWD"
	readonly script_params="$*"
	readonly script_path="${BASH_SOURCE[0]}"
	script_dir="$(dirname "$script_path")"
	script_name="$(basename "$script_path")"
	readonly script_dir script_name

	# Important to always set as we use it in the exit handler
	# shellcheck disable=SC2155
	readonly ta_none="$(tput sgr0 2> /dev/null || true)"
}

# DESC: Initialise colour variables
# ARGS: None
# OUTS: Read-only variables with ANSI control codes
# NOTE: If --no-colour was set the variables will be empty. The output of the
#       $ta_none variable after each tput is redundant during normal execution,
#       but ensures the terminal output isn't mangled when running with xtrace.
# shellcheck disable=SC2034,SC2155
function colour_init() {
	if [[ -z ${no_colour-} ]]; then
		# Text attributes
		readonly ta_bold="$(tput bold 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly ta_uscore="$(tput smul 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly ta_blink="$(tput blink 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly ta_reverse="$(tput rev 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly ta_conceal="$(tput invis 2> /dev/null || true)"
		printf '%b' "$ta_none"

		# Foreground codes
		readonly fg_black="$(tput setaf 0 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_blue="$(tput setaf 4 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_cyan="$(tput setaf 6 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_green="$(tput setaf 2 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_magenta="$(tput setaf 5 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_red="$(tput setaf 1 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_white="$(tput setaf 7 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly fg_yellow="$(tput setaf 3 2> /dev/null || true)"
		printf '%b' "$ta_none"

		# Background codes
		readonly bg_black="$(tput setab 0 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_blue="$(tput setab 4 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_cyan="$(tput setab 6 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_green="$(tput setab 2 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_magenta="$(tput setab 5 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_red="$(tput setab 1 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_white="$(tput setab 7 2> /dev/null || true)"
		printf '%b' "$ta_none"
		readonly bg_yellow="$(tput setab 3 2> /dev/null || true)"
		printf '%b' "$ta_none"
	else
		# Text attributes
		readonly ta_bold=''
		readonly ta_uscore=''
		readonly ta_blink=''
		readonly ta_reverse=''
		readonly ta_conceal=''

		# Foreground codes
		readonly fg_black=''
		readonly fg_blue=''
		readonly fg_cyan=''
		readonly fg_green=''
		readonly fg_magenta=''
		readonly fg_red=''
		readonly fg_white=''
		readonly fg_yellow=''

		# Background codes
		readonly bg_black=''
		readonly bg_blue=''
		readonly bg_cyan=''
		readonly bg_green=''
		readonly bg_magenta=''
		readonly bg_red=''
		readonly bg_white=''
		readonly bg_yellow=''
	fi
}

# DESC: Initialise Cron mode
# ARGS: None
# OUTS: $script_output: Path to the file stdout & stderr was redirected to
function cron_init() {
	if [[ -n ${cron-} ]]; then
		# Redirect all output to a temporary file
		script_output="$(mktemp --tmpdir "$script_name".XXXXX)"
		readonly script_output
		exec 3>&1 4>&2 1> "$script_output" 2>&1
	fi
}

# DESC: Acquire script lock
# ARGS: $1 (optional): Scope of script execution lock (system or user)
# OUTS: $script_lock: Path to the directory indicating we have the script lock
# NOTE: This lock implementation is extremely simple but should be reliable
#       across all platforms. It does *not* support locking a script with
#       symlinks or multiple hardlinks as there's no portable way of doing so.
#       If the lock was acquired it's automatically released on script exit.
function lock_init() {
	local lock_dir
	if [[ $1 = 'system' ]]; then
		lock_dir="/tmp/$script_name.lock"
	elif [[ $1 = 'user' ]]; then
		lock_dir="/tmp/$script_name.$UID.lock"
	else
		script_exit 'Missing or invalid argument to lock_init()!' 2
	fi

	if mkdir "$lock_dir" 2> /dev/null; then
		readonly script_lock="$lock_dir"
		verbose_print "Acquired script lock: $script_lock"
	else
		script_exit "Unable to acquire script lock: $lock_dir" 1
	fi
}

# DESC: Pretty print the provided string
# ARGS: $1 (required): Message to print (defaults to a green foreground)
#       $2 (optional): Colour to print the message with. This can be an ANSI
#                      escape code or one of the prepopulated colour variables.
#       $3 (optional): Set to any value to not append a new line to the message
# OUTS: None
function pretty_print() {
	if [[ $# -lt 1 ]]; then
		script_exit 'Missing required argument to pretty_print()!' 2
	fi

	if [[ -z ${no_colour-} ]]; then
		if [[ -n ${2-} ]]; then
			printf '%b' "$2"
		else
			printf '%b' "$fg_green"
		fi
	fi

	# Print message & reset text attributes
	if [[ -n ${3-} ]]; then
		printf '%s%b' "$1" "$ta_none"
	else
		printf '%s%b\n' "$1" "$ta_none"
	fi
}

# DESC: Only pretty_print() the provided string if verbose mode is enabled
# ARGS: $@ (required): Passed through to pretty_print() function
# OUTS: None
function verbose_print() {
	if [[ -n ${verbose-} ]]; then
		pretty_print "$@"
	fi
}

# DESC: Combines two path variables and removes any duplicates
# ARGS: $1 (required): Path(s) to join with the second argument
#       $2 (optional): Path(s) to join with the first argument
# OUTS: $build_path: The constructed path
# NOTE: Heavily inspired by: https://unix.stackexchange.com/a/40973
function build_path() {
	if [[ $# -lt 1 ]]; then
		script_exit 'Missing required argument to build_path()!' 2
	fi

	local new_path path_entry temp_path

	temp_path="$1:"
	if [[ -n ${2-} ]]; then
		temp_path="$temp_path$2:"
	fi

	new_path=
	while [[ -n $temp_path ]]; do
		path_entry="${temp_path%%:*}"
		case "$new_path:" in
			*:"$path_entry":*) ;;
			*)
				new_path="$new_path:$path_entry"
				;;
		esac
		temp_path="${temp_path#*:}"
	done

	# shellcheck disable=SC2034
	build_path="${new_path#:}"
}

# DESC: Check a binary exists in the search path
# ARGS: $1 (required): Name of the binary to test for existence
#       $2 (optional): Set to any value to treat failure as a fatal error
# OUTS: None
function check_binary() {
	if [[ $# -lt 1 ]]; then
		script_exit 'Missing required argument to check_binary()!' 2
	fi

	if ! command -v "$1" > /dev/null 2>&1; then
		if [[ -n ${2-} ]]; then
			script_exit "Missing dependency: Couldn't locate $1." 1
		else
			verbose_print "Missing dependency: $1" "${fg_red-}"
			return 1
		fi
	fi

	verbose_print "Found dependency: $1"
	return 0
}

# DESC: Validate we have superuser access as root (via sudo if requested)
# ARGS: $1 (optional): Set to any value to not attempt root access via sudo
# OUTS: None
function check_superuser() {
	local superuser
	if [[ $EUID -eq 0 ]]; then
		superuser=true
	elif [[ -z ${1-} ]]; then
		# shellcheck disable=SC2310
		if check_binary sudo; then
			verbose_print 'Sudo: Updating cached credentials ...'
			if ! sudo -v; then
				verbose_print "Sudo: Couldn't acquire credentials ..." \
					"${fg_red-}"
			else
				local test_euid
				test_euid="$(sudo -H -- "$BASH" -c 'printf "%s" "$EUID"')"
				if [[ $test_euid -eq 0 ]]; then
					superuser=true
				fi
			fi
		fi
	fi

	if [[ -z ${superuser-} ]]; then
		verbose_print 'Unable to acquire superuser credentials.' "${fg_red-}"
		return 1
	fi

	verbose_print 'Successfully acquired superuser credentials.'
	return 0
}

# DESC: Run the requested command as root (via sudo if requested)
# ARGS: $1 (optional): Set to zero to not attempt execution via sudo
#       $@ (required): Passed through for execution as root user
# OUTS: None
function run_as_root() {
	if [[ $# -eq 0 ]]; then
		script_exit 'Missing required argument to run_as_root()!' 2
	fi

	if [[ ${1-} =~ ^0$ ]]; then
		local skip_sudo=true
		shift
	fi

	if [[ $EUID -eq 0 ]]; then
		"$@"
	elif [[ -z ${skip_sudo-} ]]; then
		sudo -H -- "$@"
	else
		script_exit "Unable to run requested command as root: $*" 1
	fi
}

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# END: Helper functions (not to be modified)
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# DESC: Usage help
# ARGS: None
# OUTS: None
function script_usage() {
	cat << EOF
Usage:
	-h|--help              Displays this help
	-v|--verbose           Displays verbose output
	-nc|--no-colour         Disables colour output
	-cr|--cron              Run silently unless we encounter an error
	-i|--ipAddress         IP Address of the simulated SNMP agent
	-p|--port              The port used by the simulated SNMP agent
	-f|--snmprecFolder     The snmprec folder that contains the simulation folder used by the simulated SNMP agent
EOF
}

# DESC: Parameter parser
# ARGS: $@ (optional): Arguments provided to the script
# OUTS: Variables indicating command-line parameters and options
function parse_params() {
	local param
	while [[ $# -gt 0 ]]; do
		param="$1"
		case $param in
			-h|--help)
				script_usage
				exit 0
				;;
			-v|--verbose)
				verbose=true
				shift
				;;
			-nc|--no-colour)
				no_colour=true
				shift
				;;
			-cr|--cron)
				cron=true
				shift
				;;
			-f|--snmprecFolder)
				if [[ $# -gt 1 ]]; then
					if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
						snmprecFolderPathValue=$2
						shift 2
					else
						echo "[ERROR]: Argument for $1 is incorrect" >&2
						exit 1
					fi
				else
					echo "[ERROR]|parse_params|Argument snmprecFolder incomplete"
					exit 0
				fi
				snmprecFolder=true
				;;
			-i|--ipAddress)
				if [[ $# -gt 1 ]]; then
					if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
						ipAddressValue=$2
						shift 2
					else
						echo "[ERROR]: Argument for $1 is incorrect" >&2
						exit 1
					fi
				else
					echo "[ERROR]|parse_params|Argument ipAddress incomplete"
					exit 0
				fi
				ipAddress=true
				;;
			-p|--port)
				if [[ $# -gt 1 ]]; then
					if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
						portValue=$2
						shift 2
					else
						echo "[ERROR]: Argument for $1 is incorrect" >&2
						exit 1
					fi
				else
					echo "[ERROR]|parse_params|Argument port incomplete"
					exit 0
				fi
				port=true
				;;
			*)
				script_exit "[ERROR]|parse_params|Invalid parameter was provided: $param" 1
				;;
		esac
	done
}

# Test an IP address for validity
# Taken from: https://www.linuxjournal.com/content/validating-ip-address-bash-script
# Usage:
#  valid_ip IP_ADDRESS
#  if [[ $? -eq 0 ]]; then echo good; else echo bad; fi
#  OR
#  if valid_ip IP_ADDRESS; then echo good; else echo bad; fi
function valid_ip()
{
	local  ip=$1
	local  stat=1

	if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
		OIFS=$IFS
		IFS='.'
		ip=($ip)
		IFS=$OIFS
		[[ ${ip[0]} -le 255 && ${ip[1]} -le 255 \
			&& ${ip[2]} -le 255 && ${ip[3]} -le 255 ]]
		stat=$?
	fi
	return $stat
}

# DESC: Executes snmpsim to simulate a single SNMP agent
# ARGS: $@ (optional): Arguments provided to the script
# OUTS: None
function ExecuteSingleSnmpsimSimulation() {

	# Check if Python is installed
	if [[ "$(python3 -V)" =~ "Python 3" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Python is installed"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|Python is not installed. SNMPSIM requires Python 3.x to run" "$fg_red"
		exit 0
	fi

	# Get the major version of python
	python_version_minor=$((python3 -c 'import platform; major, minor, patch = platform.python_version_tuple(); print(minor)') 2>&1)
	pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Python Minor Version: $python_version_minor"

	# Check if snmpsim was installed for the user used to execute this script
	if [[ -f "$snmpsimPath" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|File: $snmpsimPath exists"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|File: $snmpsimPath does not exist. This Python file is used to execute snmpsim" "$fg_red"
		exit 0
	fi

	# Set the path of the variation module
	snmpsimVariationModulePath="/home/$USER/.local/lib/python3.$python_version_minor/site-packages/snmpsim/variation"

	# Check if folder snmpsimVariationModulePath exists
	if [[ -d "$snmpsimVariationModulePath" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Folder: $snmpsimVariationModulePath exists"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|Folder: $snmpsimVariationModulePath does not exist. This folder contains the Variation modules used by snmpsim to generate dynamic values in the simulation" "$fg_red"
		exit 0
	fi

	# Check if file snmpsimPidFilePath exists
	if [[ -f "$snmpsimPidFilePath" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|File: $snmpsimPidFilePath exists"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|File: $snmpsimPidFilePath does not exist. This file is used to register the PID. Required when executing snmpsim in the background" "$fg_red"
		exit 0
	fi

	# Check if file snmmpsimLogFile exists
	# if [[ -f "$snmmpsimLogFile" ]]; then
	# 	pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|File: $snmmpsimLogFile exists"
	# else
	# 	pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|File: $snmmpsimLogFile does not exist. This file is used to log any errors when executing the simulation file" "$fg_red"
	# 	exit 0
	# fi

	# Validate the IP address
	if (valid_ip $ipAddressValue); then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|IP Address: $ipAddressValue validated"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|IP Address: $ipAddressValue not valid" "$fg_red"
		exit 0
	fi

	# Validate the port number
	if [[ "$portValue" =~ ^[0-9]+$ ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Port number: $portValue validated"
	else
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Port number: $portValue not valid" "$fg_red"
		exit 0
	fi

	# Check if the port number is in the range [1024, 65535]
	# The main reason of this constraint is to avoid running snmpsim as root
	# Using port lower than 1024 implies running snmpsim as root
	if [[ $portValue -gt 65535 ]] || [[ $portValue -lt 1024 ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Port number: $portValue is not in the range [1024,65535]" "$fg_red"
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|This is required to run snmpsim without root privileges" "$fg_red"
		exit 0
	else
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Port number: $portValue is in the range [1024, 65535]"
	fi

	# Check if there is a snmpsim process already using the IP address:Port passed as argument
	# TODO: This command can be improved
	psOutput=`ps -ef | grep snmpsim`
	result=$(echo $psOutput)

	if [[ "$result" == *"--agent-udpv4-endpoint=$ipAddressValue:$portValue "* ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|There is already a process running snmpsim with IP Address and port: $ipAddressValue:$portValue" "$fg_red"
		# Get the specific process
		psOutput=`ps -ef | grep snmpsim | grep $ipAddressValue:$portValue`
		result=$(echo $psOutput)
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Process found:" "$fg_red"
		pretty_print "$result" "$fg_red"
		exit 0
	else
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|IP Address and port available to run this simulation"
	fi

	# We check if the simulation folder exists
	if [[ -d "$snmprecFolderPathValue" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Simulation folder: $snmprecFolderPathValue exists"
	else
		pretty_print "[ERROR]|ExecuteSingleSnmpsimSimulation|Simulation folder: $snmprecFolderPathValue does not exist" "$fg_red"
		exit 0
	fi

	# We check if a log simulation file exists for the simulation folder
	snmprecFolderName=$(basename ${snmprecFolderPathValue})
	logSimulationFile="$snmmpsimLogFolder$snmprecFolderName.txt"

	if [[ -f "$logSimulationFile" ]]; then
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Log for simulation file: $logSimulationFile exists"
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Log for simulation file: $logSimulationFile will be removed"

		# Since there is a simulation file, we will remove it so we can have a new log file
		rm $logSimulationFile

		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Log for simulation file: $logSimulationFile will be re-created"
		# Create a new file
		touch $logSimulationFile
	else
		pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Log for simulation file: $logSimulationFile does not exist. It will created"
		# There is no log file, we will create a new one
		touch $logSimulationFile
	fi

	# Execute the SNMPSIM command
	/usr/bin/python3 $snmpsimPath \
		--agent-udpv4-endpoint=$ipAddressValue:$portValue \
		--data-dir=$snmprecFolderPathValue \
		--variation-modules-dir=$snmpsimVariationModulePath \
		--v2c-arch \
		--pid-file=$snmpsimPidFilePath \
		--log-level=error \
		--logging-method=file:$logSimulationFile:10m \
		--daemonize
		#--process-user=$USER \
		#--process-group=$USER \

	pretty_print "[INFO]|ExecuteSingleSnmpsimSimulation|Check the log file: $logSimulationFile to troubleshoot any error"
}

# DESC: Main control flow
# ARGS: $@ (optional): Arguments provided to the script
# OUTS: None
function main() {
	trap script_trap_err ERR
	trap script_trap_exit EXIT

	script_init "$@"
	parse_params "$@"
	cron_init
	colour_init
	#lock_init system

	if [[ -n ${snmprecFolder-} ]] && [[ -n ${ipAddress-} ]] && [[ -n ${port-} ]]; then
		pretty_print "[INFO]|Main|Simulation Folder: $snmprecFolderPathValue"
		pretty_print "[INFO]|Main|IP Address: $ipAddressValue"
		pretty_print "[INFO]|Main|Port Number: $portValue"

		# Execute SNMPSIM simulation
		ExecuteSingleSnmpsimSimulation
	else
		pretty_print "[ERROR]|Main|Not all the mandatory arguments were provided" "$fg_red"
		pretty_print "[ERROR]|Main|The following arguments are mandatory:" "$fg_red"
		pretty_print "shortVersion|LongVersion:" "$fg_red"
		pretty_print "-f|--snmprecFolder" "$fg_red"
		pretty_print "-i|--ipAddress" "$fg_red"
		pretty_print "-p|--port" "$fg_red"
		pretty_print "[ERROR]|Main|Script terminated" "$fg_red"
		exit 0
	fi
}

# shellcheck source=source.sh
#source "$(dirname "${BASH_SOURCE[0]}")/source.sh"

# Invoke main with args if not sourced
# Approach via: https://stackoverflow.com/a/28776166/8787985
if ! (return 0 2> /dev/null); then
	main "$@"
fi

# vim: syntax=sh cc=80 tw=79 ts=4 sw=4 sts=4 et sr
