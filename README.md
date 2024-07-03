# SNMPSIM Tools

This repository contains scripts that can be used to interact with snmpsim simulations

## QA Device Simulator to SNMPSIM

### About

SNMPSIM is open source command line tool (running on Python) that can be used to simulate SNMP agents. Detailed information about how to use this tool can be found in the [official site](https://snmplabs.thola.io/snmpsim/).
This script converts a simulator took from the QA Device Simulator (XML file) and convert it to a simulation that can be parsed by snmpsim (snmprec file). A snmprec file is a plain text that is used by snmpsim to simulate an SNMP agent.

### How to use

For example, if you would like to convert the simulation **qaDeviceSimulator.xml** to the file **convertedSimulation.snmprec**, please proceed as follows:

```bash

qa_device_simulator_to_snmpsim.py --input="C:\MyDirectory\qaDeviceSimulator.xml" --output="C:\MyDirectory\convertedSimulation.snmprec"
```

The generated file (in this case, **convertedSimulation.snmprec**) does not need be created before the script is executed. The script will create the file in case it does not exist. If the file already exists, it will be overwritten

### Additional notes

- Some XML files generated by the QA Device Simulator contains invalid characters. For example:

```xml
<Definition OID="1.3.6.1.2.1.2.2.1.6.501" Type="OctetString" ReturnValue="&#x0;&#x0;&#x0;&#x0;&#x0;&#x14;" LogOutput="{INS}OID{INS} - {INS}ReturnValue{INS} ({INS}Type{INS})" Comment="" Delay="false" Save="false" SkipOID="false" />
```

In this case *&#x0* represents char(0) which is not valid in an XML document. This could be a consequence of a decoding issue (the QA Device simulator is decoding incorrectly a value retrieved by the device)
To surpass this constraint, this tool creates a temporary XML file containing the same information as the original XML file without the invalid characters.

## SNMPSIM Execute Single Simulation

The purpose of this bash script is to reduce the number of argument that are required to execute SNMPSIM to simulate a single SNMP agent.

### Arguments

- f|snmprecFolder: The folder that contains the simulation file (full path)
- i|ipAddress: The IP address of the simulated SNMP agent
- p|Port: The port of the simulated SNMP agent

### How to use

```bash
script_name.sh --snmprecFolder /home/myUser/mySnmprecFolder --ipAddress 10.11.12.13 --port 10161
script_name.sh -f /home/myUser/mySnmprecFolder -i 10.11.12.13 -p 10161
```
