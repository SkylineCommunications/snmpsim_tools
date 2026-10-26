/*
 * Created by SharpDevelop.
 * User: lextm
 * Date: 2008/5/11
 * Time: 12:57
 * 
 * To change this template use Tools | Options | Coding | Edit Standard Headers.
 */

// typical usage
// snmpwalk -c=public -v=1 -m=subtree localhost 1.3.6.1.2.1.1
// snmpwalk -c=public -v=2 -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
// snmpwalk -v=3 -l=noAuthNoPriv -u=neither -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
// snmpwalk -v=3 -l=authNoPriv -a=MD5 -A=authentication -u=authen -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
// snmpwalk -v=3 -l=authPriv -a=MD5 -A=authentication -x=DES -X=privacyphrase -u=privacy -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
// snmpwalk -v=3 -l=authPriv -a=SHA256 -A=authentication -x=AES -X=privacyphrase -u=privacy -m=subtree -Cr=10 localhost 1.3.6.1.2.1.1
// snmpwalk -c=public -v=2 -p=10161 -f=snmprec -o=device.snmprec localhost 1.3.6.1

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;

using Lextm.SharpSnmpLib;
using Lextm.SharpSnmpLib.Messaging;
using Lextm.SharpSnmpLib.Security;
using Mono.Options;
using System.Reflection;

namespace SnmpWalk
{
    internal static class Program
    {
        public static void Main(string[] args)
        {
            string community = "public";
            bool showHelp = false;
            bool showVersion = false;
            VersionCode version = VersionCode.V1;
            int timeout = 1000;
            int retry = 0;
            int maxRepetitions = 10;
            int port = 161;
            bool snmprecFormat = false;
            string outputFile = null;
            Levels level = Levels.Reportable;
            string user = string.Empty;
            string contextName = string.Empty;
            string authentication = string.Empty;
            string authPhrase = string.Empty;
            string privacy = string.Empty;
            string privPhrase = string.Empty;
            WalkMode mode = WalkMode.WithinSubtree;
            bool dump = false;

            OptionSet p = new OptionSet()
                .Add("c:", "Community name, (default is public)", delegate (string v) { if (v != null) community = v; })
                .Add("l:", "Security level, (default is noAuthNoPriv)", delegate (string v)
                {
                    if (v.ToUpperInvariant() == "NOAUTHNOPRIV")
                    {
                        level = Levels.Reportable;
                    }
                    else if (v.ToUpperInvariant() == "AUTHNOPRIV")
                    {
                        level = Levels.Authentication | Levels.Reportable;
                    }
                    else if (v.ToUpperInvariant() == "AUTHPRIV")
                    {
                        level = Levels.Authentication | Levels.Privacy | Levels.Reportable;
                    }
                    else
                    {
                        throw new ArgumentException("no such security mode: " + v);
                    }
                })
                .Add("a:", "Authentication method (MD5, SHA, SHA256, SHA384 or SHA512)", delegate (string v) { authentication = v; })
                .Add("A:", "Authentication passphrase", delegate (string v) { authPhrase = v; })
                .Add("x:", "Privacy method (DES, 3DES, AES, AES192 or AES256, default is DES)", delegate (string v) { privacy = v; })
                .Add("X:", "Privacy passphrase", delegate (string v) { privPhrase = v; })
                .Add("u:", "Security name", delegate (string v) { user = v; })
                .Add("C:", "Context name", delegate (string v) { contextName = v; })
                .Add("h|?|help", "Print this help information.", delegate (string v) { showHelp = v != null; })
                .Add("V", "Display version number of this application.", delegate (string v) { showVersion = v != null; })
                .Add("d", "Display message dump", delegate (string v) { dump = true; })
                .Add("t:", "Timeout value (unit is second).", delegate (string v) { timeout = int.Parse(v) * 1000; })
                .Add("r:", "Retry count (default is 0)", delegate (string v) { retry = int.Parse(v); })
                .Add("v|version:", "SNMP version (1, 2, and 3 are currently supported)", delegate (string v)
                {
                    if (v == "2c")
                    {
                        v = "2";
                    }

                    switch (int.Parse(v))
                    {
                        case 1:
                            version = VersionCode.V1;
                            break;
                        case 2:
                            version = VersionCode.V2;
                            break;
                        case 3:
                            version = VersionCode.V3;
                            break;
                        default:
                            throw new ArgumentException("no such version: " + v);
                    }
                })
                .Add("m|mode:", "WALK mode (subtree, all are supported)", delegate (string v)
                {
                    if (v == "subtree")
                    {
                        mode = WalkMode.WithinSubtree;
                    }
                    else if (v == "all")
                    {
                        mode = WalkMode.Default;
                    }
                    else
                    {
                        throw new ArgumentException("unknown argument: " + v);
                    }
                })
                .Add("Cr:", "Max-repetitions (default is 10)", delegate (string v) { maxRepetitions = int.Parse(v); })
                .Add("p|port:", "Port of the SNMP agent (default is 161)", delegate (string v)
                {
                    port = int.Parse(v);
                    if (port < 1 || port > 65535)
                    {
                        throw new ArgumentException("invalid port: " + v);
                    }
                })
                .Add("f|format:", "Output format: text (default) or snmprec (simulation file used by SNMPSIM)", delegate (string v)
                {
                    if (string.Equals(v, "snmprec", StringComparison.OrdinalIgnoreCase))
                    {
                        snmprecFormat = true;
                    }
                    else if (string.Equals(v, "text", StringComparison.OrdinalIgnoreCase))
                    {
                        snmprecFormat = false;
                    }
                    else
                    {
                        throw new ArgumentException("unknown format: " + v);
                    }
                })
                .Add("o|output:", "Write the result to this file instead of the console", delegate (string v) { outputFile = v; });

            if (args.Length == 0)
            {
                ShowHelp(p);
                return;
            }

            List<string> extra;
            try
            {
                extra = p.Parse(args);
            }
            catch (Exception ex) when (ex is OptionException || ex is ArgumentException || ex is FormatException || ex is OverflowException)
            {
                Console.Error.WriteLine(ex.Message);
                Environment.ExitCode = 1;
                return;
            }

            if (showHelp)
            {
                ShowHelp(p);
                return;
            }

            if (showVersion)
            {
                Console.WriteLine(Assembly.GetEntryAssembly()?.GetName().Version);
                return;
            }

            if (extra.Count < 1 || extra.Count > 2)
            {
                Console.Error.WriteLine("invalid variable number: " + extra.Count);
                Environment.ExitCode = 1;
                return;
            }

            IPAddress ip;
            bool parsed = IPAddress.TryParse(extra[0], out ip);
            if (!parsed)
            {
                var addresses = Dns.GetHostAddressesAsync(extra[0]);
                addresses.Wait();
                foreach (IPAddress address in
                    addresses.Result.Where(address => address.AddressFamily == AddressFamily.InterNetwork))
                {
                    ip = address;
                    break;
                }

                if (ip == null)
                {
                    Console.Error.WriteLine("invalid host or wrong IP address found: " + extra[0]);
                    Environment.ExitCode = 1;
                    return;
                }
            }

            try
            {
                ObjectIdentifier test = extra.Count == 1 ? new ObjectIdentifier("1.3.6.1.2.1") : new ObjectIdentifier(extra[1]);
                IList<Variable> result = new List<Variable>();
                IPEndPoint receiver = new IPEndPoint(ip, port);
                if (version == VersionCode.V1)
                {
                    Messenger.Walk(version, receiver, new OctetString(community), test, result, timeout, mode);
                }
                else if (version == VersionCode.V2)
                {
                    Messenger.BulkWalk(version, receiver, new OctetString(community), new OctetString(string.IsNullOrWhiteSpace(contextName) ? string.Empty: contextName),  test, result, timeout, maxRepetitions, mode, null, null);
                }
                else
                {
                    if (string.IsNullOrEmpty(user))
                    {
                        Console.Error.WriteLine("User name need to be specified for v3.");
                        Environment.ExitCode = 1;
                        return;
                    }

                    IAuthenticationProvider auth = (level & Levels.Authentication) == Levels.Authentication
                        ? GetAuthenticationProviderByName(authentication, authPhrase)
                        : DefaultAuthenticationProvider.Instance;
                    IPrivacyProvider priv = (level & Levels.Privacy) == Levels.Privacy
                        ? GetPrivacyProviderByName(privacy, privPhrase, auth)
                        : new DefaultPrivacyProvider(auth);

                    Discovery discovery = Messenger.GetNextDiscovery(SnmpType.GetBulkRequestPdu);
                    ReportMessage report = discovery.GetResponse(timeout, receiver, dump);
                    Messenger.BulkWalk(version, receiver, new OctetString(user), new OctetString(string.IsNullOrWhiteSpace(contextName) ? string.Empty : contextName),  test, result, timeout, maxRepetitions, mode, priv, report);
                }

                IList<string> lines = snmprecFormat
                    ? SnmprecFormatter.Format(result, Console.Error)
                    : result.Select(variable => variable.ToString()).ToList();

                if (string.IsNullOrEmpty(outputFile))
                {
                    foreach (string line in lines)
                    {
                        Console.WriteLine(line);
                    }
                }
                else
                {
                    // LF line endings and no byte order mark, as expected by SNMPSIM
                    File.WriteAllText(outputFile, string.Concat(lines.Select(line => line + "\n")), new UTF8Encoding(false));
                    Console.WriteLine($"{lines.Count} records written to {outputFile}");
                }
            }
            catch (SnmpException ex)
            {
                Console.Error.WriteLine(ex);
                Environment.ExitCode = 1;
            }
            catch (SocketException ex)
            {
                Console.Error.WriteLine(ex);
                Environment.ExitCode = 1;
            }
            catch (Exception ex) when (ex is ArgumentException || ex is NotSupportedException || ex is IOException || ex is UnauthorizedAccessException)
            {
                Console.Error.WriteLine(ex.Message);
                Environment.ExitCode = 1;
            }
        }

        private static IAuthenticationProvider GetAuthenticationProviderByName(string authentication, string phrase)
        {
            switch ((authentication ?? string.Empty).ToUpperInvariant())
            {
                case "MD5":
                    return new MD5AuthenticationProvider(new OctetString(phrase));
                case "SHA":
                case "SHA1":
                    return new SHA1AuthenticationProvider(new OctetString(phrase));
                case "SHA256":
                    return new SHA256AuthenticationProvider(new OctetString(phrase));
                case "SHA384":
                    return new SHA384AuthenticationProvider(new OctetString(phrase));
                case "SHA512":
                    return new SHA512AuthenticationProvider(new OctetString(phrase));
                default:
                    throw new ArgumentException("unknown authentication method: " + authentication, nameof(authentication));
            }
        }

        private static IPrivacyProvider GetPrivacyProviderByName(string privacy, string phrase, IAuthenticationProvider auth)
        {
            switch (string.IsNullOrEmpty(privacy) ? "DES" : privacy.ToUpperInvariant())
            {
                case "DES":
                    if (!DESPrivacyProvider.IsSupported)
                    {
                        throw new NotSupportedException("DES is not supported on this platform.");
                    }

                    return new DESPrivacyProvider(new OctetString(phrase), auth);
                case "3DES":
                    return new TripleDESPrivacyProvider(new OctetString(phrase), auth);
                case "AES":
                case "AES128":
                    return new AESPrivacyProvider(new OctetString(phrase), auth);
                case "AES192":
                    return new AES192PrivacyProvider(new OctetString(phrase), auth);
                case "AES256":
                    return new AES256PrivacyProvider(new OctetString(phrase), auth);
                default:
                    throw new ArgumentException("unknown privacy method: " + privacy, nameof(privacy));
            }
        }

        private static void ShowHelp(OptionSet optionSet)
        {
            Console.WriteLine("#SNMP is available at https://sharpsnmp.com");
            Console.WriteLine("snmpwalk [Options] IP-address|host-name [OID]");
            Console.WriteLine("Options:");
            optionSet.WriteOptionDescriptions(Console.Out);
        }
    }
}
