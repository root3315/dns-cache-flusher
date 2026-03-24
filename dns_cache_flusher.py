#!/usr/bin/env python3
"""
DNS Cache Flusher - Utility to flush DNS cache on Linux systems.
Supports systemd-resolved, nscd, dnsmasq, and other common caching services.
"""

import subprocess
import sys
import os
import argparse
from pathlib import Path


class DNSCacheFlusher:
    """Handles DNS cache flushing across different Linux DNS caching services."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.services = {
            'systemd-resolved': self._flush_systemd_resolved,
            'nscd': self._flush_nscd,
            'dnsmasq': self._flush_dnsmasq,
            'unbound': self._flush_unbound,
            'named': self._flush_named,
        }
        self.flushed_services = []
        self.failed_services = []

    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def check_service_running(self, service_name):
        """Check if a systemd service is currently running."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def check_command_exists(self, command):
        """Check if a command exists in the system PATH."""
        return subprocess.run(
            ['which', command],
            capture_output=True,
            timeout=5
        ).returncode == 0

    def _flush_systemd_resolved(self):
        """Flush DNS cache for systemd-resolved service."""
        self.log("Attempting to flush systemd-resolved cache...")
        
        if not self.check_service_running('systemd-resolved'):
            self.log("  systemd-resolved is not running")
            return False

        try:
            result = subprocess.run(
                ['resolvectl', 'flush-caches'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully flushed systemd-resolved cache")
                return True
            
            if 'Unknown command' in result.stderr:
                result = subprocess.run(
                    ['systemd-resolve', '--flush-caches'],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if result.returncode == 0:
                    self.log("  Successfully flushed using systemd-resolve")
                    return True

            self.log(f"  Failed: {result.stderr.strip()}")
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.log(f"  Error: {str(e)}")
            return False

    def _flush_nscd(self):
        """Flush DNS cache for nscd (Name Service Cache Daemon)."""
        self.log("Attempting to flush nscd cache...")
        
        if not self.check_service_running('nscd'):
            self.log("  nscd is not running")
            return False

        try:
            result = subprocess.run(
                ['nscd', '-i', 'hosts'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully flushed nscd hosts cache")
                return True
            
            self.log(f"  Failed: {result.stderr.strip()}")
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.log(f"  Error: {str(e)}")
            return False

    def _flush_dnsmasq(self):
        """Flush DNS cache for dnsmasq service."""
        self.log("Attempting to flush dnsmasq cache...")
        
        if not self.check_service_running('dnsmasq'):
            self.log("  dnsmasq is not running")
            return False

        try:
            result = subprocess.run(
                ['killall', '-USR2', 'dnsmasq'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully signaled dnsmasq to flush cache")
                return True
            
            self.log(f"  Failed: {result.stderr.strip()}")
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.log(f"  Error: {str(e)}")
            return False

    def _flush_unbound(self):
        """Flush DNS cache for unbound DNS resolver."""
        self.log("Attempting to flush unbound cache...")
        
        if not self.check_service_running('unbound'):
            self.log("  unbound is not running")
            return False

        try:
            result = subprocess.run(
                ['unbound-control', 'flush_zone', '.'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully flushed unbound cache")
                return True
            
            result = subprocess.run(
                ['unbound-control', 'flush_request'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully flushed unbound request cache")
                return True
            
            self.log(f"  Failed: {result.stderr.strip()}")
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.log(f"  Error: {str(e)}")
            return False

    def _flush_named(self):
        """Flush DNS cache for BIND named service."""
        self.log("Attempting to flush BIND named cache...")
        
        if not self.check_service_running('named'):
            self.log("  named is not running")
            return False

        try:
            result = subprocess.run(
                ['rndc', 'flush'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                self.log("  Successfully flushed BIND named cache")
                return True
            
            self.log(f"  Failed: {result.stderr.strip()}")
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.log(f"  Error: {str(e)}")
            return False

    def detect_active_services(self):
        """Detect which DNS caching services are active on the system."""
        active = []
        for service_name in self.services.keys():
            if self.check_service_running(service_name):
                active.append(service_name)
                self.log(f"Detected active service: {service_name}")
        return active

    def flush_all(self):
        """Attempt to flush all detected DNS caches."""
        print("DNS Cache Flusher - Starting flush process")
        print("=" * 50)
        
        active_services = self.detect_active_services()
        
        if not active_services:
            print("No known DNS caching services detected as running.")
            print("Your system may not be using a DNS cache, or uses an unsupported service.")
            self._flush_kernel_dns_cache()
            return len(self.flushed_services) > 0

        print(f"Found {len(active_services)} active DNS caching service(s):")
        for svc in active_services:
            print(f"  - {svc}")
        print()

        for service_name in active_services:
            flush_func = self.services[service_name]
            if flush_func():
                self.flushed_services.append(service_name)
            else:
                self.failed_services.append(service_name)

        self._flush_kernel_dns_cache()
        self._print_summary()
        
        return len(self.flushed_services) > 0

    def _flush_kernel_dns_cache(self):
        """Flush kernel DNS cache if present."""
        self.log("Checking for kernel DNS cache...")
        
        conntrack_path = Path('/proc/sys/net/netfilter/nf_conntrack_count')
        if conntrack_path.exists():
            try:
                result = subprocess.run(
                    ['conntrack', '-F'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.log("  Flushed kernel conntrack table")
                    self.flushed_services.append('kernel-conntrack')
                    return
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        self.log("  No kernel DNS cache found or conntrack not available")

    def _print_summary(self):
        """Print a summary of the flush operation."""
        print()
        print("=" * 50)
        print("Flush Summary:")
        
        if self.flushed_services:
            print(f"  Successfully flushed: {', '.join(self.flushed_services)}")
        
        if self.failed_services:
            print(f"  Failed to flush: {', '.join(self.failed_services)}")
        
        if not self.flushed_services and not self.failed_services:
            print("  No services were flushed.")
        
        print()
        if self.flushed_services:
            print("DNS cache has been flushed successfully!")
            sys.exit(0)
        else:
            print("No DNS caches were flushed. Check verbose output for details.")
            sys.exit(1)


def check_root_privileges():
    """Check if the script is running with root privileges."""
    if os.geteuid() != 0:
        print("Error: This script requires root privileges to flush DNS caches.")
        print("Please run with: sudo python3 dns_cache_flusher.py")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Flush DNS cache on Linux systems',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 dns_cache_flusher.py
  sudo python3 dns_cache_flusher.py --verbose
  sudo python3 dns_cache_flusher.py --service systemd-resolved
        """
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '-s', '--service',
        choices=['systemd-resolved', 'nscd', 'dnsmasq', 'unbound', 'named'],
        help='Flush only the specified service'
    )
    parser.add_argument(
        '--list-services',
        action='store_true',
        help='List detected DNS caching services without flushing'
    )

    args = parser.parse_args()

    check_root_privileges()

    flusher = DNSCacheFlusher(verbose=args.verbose)

    if args.list_services:
        print("Detected DNS caching services:")
        active = flusher.detect_active_services()
        if active:
            for svc in active:
                print(f"  - {svc} (running)")
            for svc in flusher.services.keys():
                if svc not in active:
                    print(f"  - {svc} (not running)")
        else:
            print("  No DNS caching services detected")
        sys.exit(0)

    if args.service:
        print(f"Flushing only {args.service}...")
        if flusher.services[args.service]():
            print(f"Successfully flushed {args.service}")
            sys.exit(0)
        else:
            print(f"Failed to flush {args.service}")
            sys.exit(1)

    flusher.flush_all()


if __name__ == '__main__':
    main()
