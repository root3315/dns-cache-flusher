#!/usr/bin/env python3
"""Unit tests for DNS Cache Flusher."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import sys
import os

from dns_cache_flusher import DNSCacheFlusher, check_root_privileges


class TestDNSCacheFlusherInit(unittest.TestCase):
    """Tests for DNSCacheFlusher initialization."""

    def test_init_default(self):
        flusher = DNSCacheFlusher()
        self.assertFalse(flusher.verbose)
        self.assertEqual(len(flusher.services), 5)
        self.assertEqual(flusher.flushed_services, [])
        self.assertEqual(flusher.failed_services, [])

    def test_init_verbose(self):
        flusher = DNSCacheFlusher(verbose=True)
        self.assertTrue(flusher.verbose)

    def test_services_dict_keys(self):
        flusher = DNSCacheFlusher()
        expected_services = {
            'systemd-resolved', 'nscd', 'dnsmasq', 'unbound', 'named'
        }
        self.assertEqual(set(flusher.services.keys()), expected_services)


class TestLogMethod(unittest.TestCase):
    """Tests for the log method."""

    def test_log_verbose_enabled(self):
        flusher = DNSCacheFlusher(verbose=True)
        with patch('builtins.print') as mock_print:
            flusher.log("Test message")
            mock_print.assert_called_once_with("Test message")

    def test_log_verbose_disabled(self):
        flusher = DNSCacheFlusher(verbose=False)
        with patch('builtins.print') as mock_print:
            flusher.log("Test message")
            mock_print.assert_not_called()


class TestCheckServiceRunning(unittest.TestCase):
    """Tests for check_service_running method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher()

    @patch('dns_cache_flusher.subprocess.run')
    def test_service_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='active')
        result = self.flusher.check_service_running('systemd-resolved')
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['systemctl', 'is-active', 'systemd-resolved'],
            capture_output=True,
            text=True,
            timeout=10
        )

    @patch('dns_cache_flusher.subprocess.run')
    def test_service_not_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=3, stdout='inactive')
        result = self.flusher.check_service_running('systemd-resolved')
        self.assertFalse(result)

    @patch('dns_cache_flusher.subprocess.run')
    def test_timeout_exception(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='systemctl', timeout=10)
        result = self.flusher.check_service_running('systemd-resolved')
        self.assertFalse(result)

    @patch('dns_cache_flusher.subprocess.run')
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = self.flusher.check_service_running('systemd-resolved')
        self.assertFalse(result)


class TestCheckCommandExists(unittest.TestCase):
    """Tests for check_command_exists method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher()

    @patch('dns_cache_flusher.subprocess.run')
    def test_command_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = self.flusher.check_command_exists('resolvectl')
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['which', 'resolvectl'],
            capture_output=True,
            timeout=5
        )

    @patch('dns_cache_flusher.subprocess.run')
    def test_command_not_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = self.flusher.check_command_exists('nonexistent')
        self.assertFalse(result)

    @patch('dns_cache_flusher.subprocess.run')
    def test_timeout_exception(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = self.flusher.check_command_exists('resolvectl')
        self.assertFalse(result)


class TestFlushSystemdResolved(unittest.TestCase):
    """Tests for _flush_systemd_resolved method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success_resolvectl(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.flusher._flush_systemd_resolved()
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['resolvectl', 'flush-caches'],
            capture_output=True,
            text=True,
            timeout=15
        )

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_fallback_systemd_resolve(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout='', stderr='Unknown command'),
            MagicMock(returncode=0, stdout='', stderr='')
        ]
        result = self.flusher._flush_systemd_resolved()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_service_not_running(self, mock_check, mock_run):
        mock_check.return_value = False
        result = self.flusher._flush_systemd_resolved()
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_failure(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Error occurred')
        result = self.flusher._flush_systemd_resolved()
        self.assertFalse(result)


class TestFlushNscd(unittest.TestCase):
    """Tests for _flush_nscd method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.flusher._flush_nscd()
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['nscd', '-i', 'hosts'],
            capture_output=True,
            text=True,
            timeout=15
        )

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_service_not_running(self, mock_check, mock_run):
        mock_check.return_value = False
        result = self.flusher._flush_nscd()
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_failure(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Failed')
        result = self.flusher._flush_nscd()
        self.assertFalse(result)


class TestFlushDnsmasq(unittest.TestCase):
    """Tests for _flush_dnsmasq method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.flusher._flush_dnsmasq()
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['killall', '-USR2', 'dnsmasq'],
            capture_output=True,
            text=True,
            timeout=15
        )

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_service_not_running(self, mock_check, mock_run):
        mock_check.return_value = False
        result = self.flusher._flush_dnsmasq()
        self.assertFalse(result)


class TestFlushUnbound(unittest.TestCase):
    """Tests for _flush_unbound method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success_flush_zone(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.flusher._flush_unbound()
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['unbound-control', 'flush_zone', '.'],
            capture_output=True,
            text=True,
            timeout=15
        )

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success_flush_request(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout='', stderr='Unknown command'),
            MagicMock(returncode=0, stdout='', stderr='')
        ]
        result = self.flusher._flush_unbound()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_service_not_running(self, mock_check, mock_run):
        mock_check.return_value = False
        result = self.flusher._flush_unbound()
        self.assertFalse(result)


class TestFlushNamed(unittest.TestCase):
    """Tests for _flush_named method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_success(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = self.flusher._flush_named()
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['rndc', 'flush'],
            capture_output=True,
            text=True,
            timeout=15
        )

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_service_not_running(self, mock_check, mock_run):
        mock_check.return_value = False
        result = self.flusher._flush_named()
        self.assertFalse(result)

    @patch('dns_cache_flusher.subprocess.run')
    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_flush_failure(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Error')
        result = self.flusher._flush_named()
        self.assertFalse(result)


class TestDetectActiveServices(unittest.TestCase):
    """Tests for detect_active_services method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_no_active_services(self, mock_check):
        mock_check.return_value = False
        result = self.flusher.detect_active_services()
        self.assertEqual(result, [])
        self.assertEqual(mock_check.call_count, 5)

    @patch.object(DNSCacheFlusher, 'check_service_running')
    def test_some_active_services(self, mock_check):
        def side_effect(service):
            return service in ['systemd-resolved', 'nscd']
        mock_check.side_effect = side_effect
        result = self.flusher.detect_active_services()
        self.assertEqual(result, ['systemd-resolved', 'nscd'])


class TestFlushKernelDnsCache(unittest.TestCase):
    """Tests for _flush_kernel_dns_cache method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch('dns_cache_flusher.Path.exists')
    @patch('dns_cache_flusher.subprocess.run')
    def test_flush_kernel_cache_success(self, mock_run, mock_exists):
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        self.flusher._flush_kernel_dns_cache()
        self.assertIn('kernel-conntrack', self.flusher.flushed_services)

    @patch('dns_cache_flusher.Path.exists')
    @patch('dns_cache_flusher.subprocess.run')
    def test_flush_kernel_cache_failure(self, mock_run, mock_exists):
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='Error')
        self.flusher._flush_kernel_dns_cache()
        self.assertNotIn('kernel-conntrack', self.flusher.flushed_services)

    @patch('dns_cache_flusher.Path.exists')
    def test_kernel_cache_path_not_exists(self, mock_exists):
        mock_exists.return_value = False
        self.flusher._flush_kernel_dns_cache()
        self.assertNotIn('kernel-conntrack', self.flusher.flushed_services)

    @patch('dns_cache_flusher.Path.exists')
    @patch('dns_cache_flusher.subprocess.run')
    def test_flush_kernel_cache_timeout(self, mock_run, mock_exists):
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='conntrack', timeout=10)
        self.flusher._flush_kernel_dns_cache()
        self.assertNotIn('kernel-conntrack', self.flusher.flushed_services)


class TestFlushAll(unittest.TestCase):
    """Tests for flush_all method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher(verbose=True)

    @patch.object(DNSCacheFlusher, 'detect_active_services')
    @patch.object(DNSCacheFlusher, '_flush_kernel_dns_cache')
    @patch.object(DNSCacheFlusher, '_print_summary')
    def test_flush_all_no_active_services(self, mock_summary, mock_kernel, mock_detect):
        mock_detect.return_value = []
        with patch('builtins.print'):
            result = self.flusher.flush_all()
        self.assertFalse(result)
        mock_kernel.assert_called_once()
        mock_summary.assert_not_called()

    @patch.object(DNSCacheFlusher, 'detect_active_services')
    @patch.object(DNSCacheFlusher, '_flush_kernel_dns_cache')
    @patch.object(DNSCacheFlusher, '_print_summary')
    def test_flush_all_with_active_services(self, mock_summary, mock_kernel, mock_detect):
        mock_detect.return_value = ['systemd-resolved']
        with patch.object(self.flusher, '_flush_systemd_resolved', return_value=True):
            with patch('builtins.print'):
                result = self.flusher.flush_all()
        self.assertTrue(result)
        self.assertEqual(self.flusher.flushed_services, ['systemd-resolved'])
        self.assertEqual(self.flusher.failed_services, [])
        mock_kernel.assert_called_once()
        mock_summary.assert_called_once()

    @patch.object(DNSCacheFlusher, 'detect_active_services')
    @patch.object(DNSCacheFlusher, '_flush_kernel_dns_cache')
    @patch.object(DNSCacheFlusher, '_print_summary')
    def test_flush_all_with_failures(self, mock_summary, mock_kernel, mock_detect):
        mock_detect.return_value = ['systemd-resolved', 'nscd']
        with patch.object(self.flusher, '_flush_systemd_resolved', return_value=True):
            with patch.object(self.flusher, '_flush_nscd', return_value=False):
                with patch('builtins.print'):
                    result = self.flusher.flush_all()
        self.assertTrue(result)
        self.assertEqual(self.flusher.flushed_services, ['systemd-resolved'])
        self.assertEqual(self.flusher.failed_services, ['nscd'])


class TestPrintSummary(unittest.TestCase):
    """Tests for _print_summary method."""

    def setUp(self):
        self.flusher = DNSCacheFlusher()

    @patch('builtins.print')
    @patch('dns_cache_flusher.sys.exit')
    def test_summary_success(self, mock_exit, mock_print):
        self.flusher.flushed_services = ['systemd-resolved']
        self.flusher._print_summary()
        mock_exit.assert_called_once_with(0)

    @patch('builtins.print')
    @patch('dns_cache_flusher.sys.exit')
    def test_summary_failure(self, mock_exit, mock_print):
        self.flusher.failed_services = ['systemd-resolved']
        self.flusher._print_summary()
        mock_exit.assert_called_once_with(1)

    @patch('builtins.print')
    @patch('dns_cache_flusher.sys.exit')
    def test_summary_empty(self, mock_exit, mock_print):
        self.flusher._print_summary()
        mock_exit.assert_called_once_with(1)


class TestCheckRootPrivileges(unittest.TestCase):
    """Tests for check_root_privileges function."""

    @patch('dns_cache_flusher.os.geteuid')
    @patch('dns_cache_flusher.sys.exit')
    def test_not_root(self, mock_exit, mock_geteuid):
        mock_geteuid.return_value = 1000
        check_root_privileges()
        mock_exit.assert_called_once_with(1)

    @patch('dns_cache_flusher.os.geteuid')
    @patch('dns_cache_flusher.sys.exit')
    def test_is_root(self, mock_exit, mock_geteuid):
        mock_geteuid.return_value = 0
        check_root_privileges()
        mock_exit.assert_not_called()


class TestIntegration(unittest.TestCase):
    """Integration tests for DNSCacheFlusher."""

    @patch('dns_cache_flusher.subprocess.run')
    @patch('dns_cache_flusher.sys.exit')
    def test_full_flush_scenario(self, mock_exit, mock_run):
        def side_effect(*args, **kwargs):
            if args[0][0] == 'systemctl':
                service = args[0][2]
                if service == 'systemd-resolved':
                    return MagicMock(returncode=0, stdout='active')
                return MagicMock(returncode=3, stdout='inactive')
            return MagicMock(returncode=0, stdout='', stderr='')

        mock_run.side_effect = side_effect

        flusher = DNSCacheFlusher(verbose=True)
        active = flusher.detect_active_services()
        self.assertEqual(active, ['systemd-resolved'])

        with patch.object(flusher, '_flush_systemd_resolved', return_value=True):
            with patch('builtins.print'):
                result = flusher.flush_all()
        self.assertTrue(result)
        mock_exit.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()
