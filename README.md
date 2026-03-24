# DNS Cache Flusher

Quick utility to flush DNS cache on Linux systems. I wrote this because I kept forgetting which command to run depending on which distro I was using.

## Why This Exists

Different Linux distributions use different DNS caching services:
- Modern Ubuntu/Debian → systemd-resolved
- Some RHEL/CentOS → nscd
- Custom setups → dnsmasq, unbound, or BIND

This script detects what's running and flushes the right cache. No more guessing.

## Requirements

- Python 3.6+
- Root/sudo access (obviously, you're flushing system caches)
- systemd (for service detection)

No external dependencies. Just stdlib.

## Usage

Basic flush:
```bash
sudo python3 dns_cache_flusher.py
```

Verbose mode (shows what it's doing):
```bash
sudo python3 dns_cache_flusher.py --verbose
```

List detected services without flushing:
```bash
sudo python3 dns_cache_flusher.py --list-services
```

Flush a specific service only:
```bash
sudo python3 dns_cache_flusher.py --service systemd-resolved
```

## Supported Services

| Service | Flush Method |
|---------|-------------|
| systemd-resolved | `resolvectl flush-caches` |
| nscd | `nscd -i hosts` |
| dnsmasq | `killall -USR2 dnsmasq` |
| unbound | `unbound-control flush_zone` |
| named (BIND) | `rndc flush` |

It also attempts to flush the kernel conntrack table if available.

## How It Works

1. Checks which DNS caching services are currently running via systemctl
2. Calls the appropriate flush command for each active service
3. Reports what succeeded and what failed

## Exit Codes

- `0` - At least one cache was flushed successfully
- `1` - No caches were flushed (either nothing running or all flushes failed)

## Installation

Clone it somewhere:
```bash
git clone <repo> /opt/dns-cache-flusher
cd /opt/dns-cache-flusher
```

Make it executable:
```bash
chmod +x dns_cache_flusher.py
```

Optionally symlink it:
```bash
sudo ln -s /opt/dns-cache-flusher/dns_cache_flusher.py /usr/local/bin/dnsflush
```

Then just run `dnsflush` whenever.

## Notes

- If you're on a system without any DNS caching service, this will tell you that
- The script won't break anything if a service doesn't support flushing
- Feel free to add support for more services by extending the `services` dict

## License

Do whatever you want with it.
