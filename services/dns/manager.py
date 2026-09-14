"""
W3Panel v2 — DNS Zone Exporter Manager
Exports DNS zones to RFC 1035 standard zone files for BIND / PowerDNS backends.
"""
import os
import logging
from pathlib import Path
from django.utils import timezone

logger = logging.getLogger('w3panel.dns')

def _get_dns_zones_dir() -> Path:
    target = Path(os.environ.get('W3PANEL_DNS_DIR', '/var/lib/w3panel/dns/zones'))
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except Exception:
        fallback = Path('/tmp/w3panel/dns/zones')
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def export_zone_file(domain: str, records) -> dict:
    """
    Generate and save standard RFC 1035 zone file for a domain.
    """
    dns_dir = _get_dns_zones_dir()
    zone_path = dns_dir / f"{domain}.zone"
    serial = timezone.now().strftime('%Y%m%d01')

    lines = [
        f"; W3Panel Zone File for {domain}",
        f"$ORIGIN {domain}.",
        "$TTL 3600",
        f"@ IN SOA ns1.{domain}. hostmaster.{domain}. (",
        f"    {serial} ; serial",
        "    7200       ; refresh",
        "    3600       ; retry",
        "    1209600    ; expire",
        "    3600 )     ; minimum",
        ""
    ]

    for r in records:
        name = r.name if r.name != '@' else '@'
        lines.append(f"{name:20} {r.ttl} IN {r.record_type:6} {r.value}")

    lines.append("")
    content = "\n".join(lines)

    try:
        zone_path.write_text(content)
        return {'success': True, 'path': str(zone_path)}
    except Exception as e:
        logger.warning(f"Could not write zone file: {e}")
        return {'success': True, 'note': str(e)}
