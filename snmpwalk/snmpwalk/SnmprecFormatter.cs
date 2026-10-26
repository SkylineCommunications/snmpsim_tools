using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

using Lextm.SharpSnmpLib;

namespace SnmpWalk
{
    /// <summary>
    /// Formats SNMP variables as snmprec records (OID|tag|value), the simulation format used by SNMPSIM.
    /// </summary>
    internal static class SnmprecFormatter
    {
        /// <summary>
        /// Formats the variables sorted by OID (required by SNMPSIM to answer GETNEXT/GETBULK requests).
        /// Duplicated OIDs and types without snmprec representation (e.g. noSuchInstance) are skipped and reported to <paramref name="warnings"/>.
        /// </summary>
        public static IList<string> Format(IEnumerable<Variable> variables, TextWriter warnings)
        {
            var lines = new List<string>();
            ObjectIdentifier previousId = null;

            foreach (Variable variable in variables.OrderBy(variable => variable.Id))
            {
                if (previousId != null && variable.Id.Equals(previousId))
                {
                    warnings.WriteLine($"Duplicated record skipped: {variable.Id}");
                    continue;
                }

                previousId = variable.Id;

                string value = FormatValue(variable.Data);
                if (value == null)
                {
                    warnings.WriteLine($"Record skipped, type {variable.Data.TypeCode} is not supported by snmprec: {variable.Id}");
                    continue;
                }

                lines.Add($"{variable.Id}|{value}");
            }

            return lines;
        }

        private static string FormatValue(ISnmpData data)
        {
            switch (data.TypeCode)
            {
                case SnmpType.Integer32:
                    return "2|" + ((Integer32)data).ToInt32().ToString(CultureInfo.InvariantCulture);
                case SnmpType.OctetString:
                    return FormatOctets(((OctetString)data).GetRaw());
                case SnmpType.Null:
                    return "5|";
                case SnmpType.ObjectIdentifier:
                    return "6|" + data;
                case SnmpType.IPAddress:
                    return "64|" + data;
                case SnmpType.Counter32:
                    return "65|" + ((Counter32)data).ToUInt32().ToString(CultureInfo.InvariantCulture);
                case SnmpType.Gauge32:
                    return "66|" + ((Gauge32)data).ToUInt32().ToString(CultureInfo.InvariantCulture);
                case SnmpType.TimeTicks:
                    return "67|" + ((TimeTicks)data).ToUInt32().ToString(CultureInfo.InvariantCulture);
                case SnmpType.Opaque:
                    return "68x|" + ToHex(((Opaque)data).GetRaw());
                case SnmpType.Counter64:
                    return "70|" + ((Counter64)data).ToUInt64().ToString(CultureInfo.InvariantCulture);
                default:
                    return null;
            }
        }

        // Plain text is only used for printable ASCII without trailing whitespace (SNMPSIM trims the end of each line).
        // Other values (e.g. MAC addresses, line breaks) are written in hexadecimal with the tag suffix 'x'.
        private static string FormatOctets(byte[] bytes)
        {
            bool plainText = bytes.All(value => value >= 0x20 && value <= 0x7E) && (bytes.Length == 0 || bytes[bytes.Length - 1] != 0x20);

            return plainText ? "4|" + Encoding.ASCII.GetString(bytes) : "4x|" + ToHex(bytes);
        }

        private static string ToHex(byte[] bytes)
        {
            return string.Concat(bytes.Select(value => value.ToString("x2", CultureInfo.InvariantCulture)));
        }
    }
}
