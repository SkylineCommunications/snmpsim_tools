# SNMPSIM Container

The files in this folder build a container image that runs one simulated SNMP agent with [snmpsim](https://docs.lextudio.com/snmpsim/). The simulation file (snmprec) is copied into the image, so the image runs without any other file: with Podman on a Linux host, or on a Kubernetes cluster.

- [Containerfile](Containerfile): definition of the image
- [requirements.txt](requirements.txt): Python packages installed in the image, with pinned versions
- [build.sh](build.sh): builds the image of one simulation file
- [run.sh](run.sh): runs an image with Podman
- [kubernetes](kubernetes/README.md): template of the Kubernetes manifest and steps to deploy an image on Kubernetes

## Prerequisites

- Podman (tested with Podman 4.9 on Ubuntu 24.04). On Ubuntu/Debian, install it with `sudo apt install podman`
- A simulation file (snmprec), e.g., created with [snmpwalk_to_snmpsim.py](../scripts/snmpwalk_to_snmpsim.py), [qa_device_simulator_to_snmpsim.py](../scripts/qa_device_simulator_to_snmpsim.py) or the [snmpwalk](../snmpwalk/README.md) tool
- Optionally, the Net-SNMP tools to test the simulated agent. On Ubuntu/Debian, install them with `sudo apt install snmp`

Python and snmpsim do not have to be installed on the host: they are part of the image.

## Build an image

Run the commands in the `container` folder as a regular user (without `sudo`).

1. Copy the simulation file to the `data` folder:

   ```bash
   mkdir -p data
   cp ~/myDevice.snmprec data/my_device.snmprec
   ```

   The build can only use files inside the `container` folder. The `data` folder is excluded from the repository by [.gitignore](.gitignore), because simulation files can contain data of real devices.

2. Build the image:

   ```bash
   ./build.sh data/my_device.snmprec my_device:1.0.0
   ```

   The image will be stored as `localhost/my_device:1.0.0`. You can check this with `podman images`.

Keep the following in mind:

- Use lowercase letters, digits, `_` and `-` in the image name
- Use a new version for every build of the same image. A running simulation on Kubernetes is only replaced when the version changes
- The name of the simulation file does not matter. In the image, the file is always named `public.snmprec`, so the agent answers to the SNMP community `public`

## Run an image

1. Start the simulated agent on a UDP port of the host:

   ```bash
   ./run.sh my_device:1.0.0 10161
   ```

   A container named `snmpsim_my_device` (the image name without the version) will start. An existing container with this name is replaced.

2. Test the simulated agent:

   ```bash
   snmpget -v2c -c public localhost:10161 1.3.6.1.2.1.1.1.0
   ```

   The agent will answer a few seconds after the start.

Each simulated agent needs its own port. By default, rootless Podman cannot use host ports below 1024 (e.g., 161).

To run `./run.sh` without arguments, create a file named `.env` in the `container` folder with the image and the port. This file is excluded from the repository.

```bash
DEVICE_NAME=my_device:1.0.0
PORT=10161
```

To follow the logs or to stop the simulated agent:

```bash
podman logs -f snmpsim_my_device
podman rm -f snmpsim_my_device
```

## Image details

- Base image: `python:3.12-slim`. With Python 3.13, snmpsim takes much longer to start (see the comments in the [Containerfile](Containerfile))
- User: `snmpsim` (UID and GID 10001), not root
- Port: 1161/udp in the container, because a non-root user cannot use ports below 1024. Publish it on another port, e.g., `10161:1161/udp` with Podman, or port 161 of a Kubernetes service
- SNMPv1 and SNMPv2c: community `public`
- SNMPv3 (default user of snmpsim): user `simulator`, security level `authPriv`, authentication MD5 with key `auctoritas`, privacy DES with key `privatus`, and context name `public`. For example:

  ```bash
  snmpget -v3 -u simulator -l authPriv -a MD5 -A auctoritas -x DES -X privatus -n public localhost:10161 1.3.6.1.2.1.1.1.0
  ```

- Start: before it answers, snmpsim indexes the simulation file in `/tmp/snmpsim`. This is the only folder where the container writes
- Logs: written to the standard output, so they are shown by `podman logs` and `kubectl logs`
- Stop: snmpsim stops cleanly on SIGINT, the stop signal of the image

## Deploy on Kubernetes

[kubernetes/README.md](kubernetes/README.md) describes how to run an image on a Kubernetes cluster without a container registry: export the image to a file, import it on the nodes, and deploy it with the manifest template.
