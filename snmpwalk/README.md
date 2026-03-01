# SNMP Walk

A C# console application that performs SNMP walk operations against SNMP agents. It supports SNMPv1, SNMPv2c, and SNMPv3.

## Prerequisites

- [.NET 8.0 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)

## Build and Run

### Run directly with the .NET CLI

From the `snmpwalk` directory, run:

```bash
dotnet run --project snmpwalk -- [Options] IP-address|host-name [OID]
```

## Usage

```
snmpwalk [Options] IP-address|host-name [OID]
```

If no OID is specified, the walk starts at `1.3.6.1.2.1` by default.

### Options

| Option | Description |
|---|---|
| `-c <community>` | Community name (default: `public`) |
| `-v <version>` | SNMP version: `1`, `2`, `2c`, or `3` |
| `-m <mode>` | Walk mode: `subtree` (default) or `all` |
| `-Cr <n>` | Max-repetitions for bulk walk (default: `10`) |
| `-t <seconds>` | Timeout in seconds (default: `1`) |
| `-r <count>` | Retry count (default: `0`) |
| `-l <level>` | SNMPv3 security level: `noAuthNoPriv`, `authNoPriv`, or `authPriv` |
| `-a <method>` | SNMPv3 authentication method: `MD5` or `SHA` |
| `-A <passphrase>` | SNMPv3 authentication passphrase |
| `-x <method>` | SNMPv3 privacy method (e.g. `DES`) |
| `-X <passphrase>` | SNMPv3 privacy passphrase |
| `-u <username>` | SNMPv3 security name |
| `-C <contextname>` | SNMPv3 context name |
| `-d` | Display message dump |
| `-V` | Display application version |
| `-h`, `-?`, `--help` | Print help information |

### Examples

**SNMPv1**
```bash
snmpwalk -c=public -v=1 -m=subtree localhost 1.3.6.1.2.1.1
```

**SNMPv2c**
```bash
snmpwalk -c=public -v=2 -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
```

**SNMPv3 – no authentication, no privacy**
```bash
snmpwalk -v=3 -l=noAuthNoPriv -u=neither -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
```

**SNMPv3 – authentication, no privacy**
```bash
snmpwalk -v=3 -l=authNoPriv -a=MD5 -A=authentication -u=authen -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
```

**SNMPv3 – authentication and privacy**
```bash
snmpwalk -v=3 -l=authPriv -a=MD5 -A=authentication -x=DES -X=privacyphrase -u=privacy -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
```

## Generate a Single Executable

Use `dotnet publish` to produce a self-contained, single-file executable. Run the command from the `snmpwalk` directory.

### Windows (x64)

```bash
dotnet publish snmpwalk -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

### Linux (x64)

```bash
dotnet publish snmpwalk -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true
```

### macOS (x64)

```bash
dotnet publish snmpwalk -c Release -r osx-x64 --self-contained true -p:PublishSingleFile=true
```

### macOS (Apple Silicon / ARM64)

```bash
dotnet publish snmpwalk -c Release -r osx-arm64 --self-contained true -p:PublishSingleFile=true
```

The output executable is placed in:

```
snmpwalk/bin/Release/net8.0/<runtime-identifier>/publish/
```
