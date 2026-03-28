"""
Management command: check system requirements before installation.
Usage: python manage.py check_requirements
"""
import shutil
import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify system requirements for Lite Hosting Panel'

    def handle(self, *args, **options):
        errors = []
        import platform

        # Architecture
        arch = platform.machine()
        supported_arches = ('x86_64', 'aarch64', 'arm64', 'armv7l')
        if arch in supported_arches:
            self.stdout.write(self.style.SUCCESS(f'✓ Architecture: {arch}'))
        else:
            errors.append(f'Unsupported architecture: {arch}')

        # Python version
        if sys.version_info < (3, 8):
            errors.append(f'Python >= 3.8 required (found {sys.version})')
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Python {sys.version.split()[0]}'))

        # OpenLiteSpeed
        if shutil.which('lswsctrl') or shutil.which('/usr/local/lsws/bin/lswsctrl'):
            self.stdout.write(self.style.SUCCESS('✓ OpenLiteSpeed found'))
        else:
            errors.append('OpenLiteSpeed not found. Install from https://openlitespeed.org/')

        # MariaDB / MySQL
        if shutil.which('mysql'):
            try:
                result = subprocess.run(['mysql', '--version'], capture_output=True, text=True, timeout=5)
                self.stdout.write(self.style.SUCCESS(f'✓ MySQL/MariaDB: {result.stdout.strip()}'))
            except Exception:
                errors.append('MySQL/MariaDB found but not responding.')
        else:
            errors.append('MySQL/MariaDB not found. Install mariadb-server.')

        # RAM
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        kb = int(line.split()[1])
                        gb = kb / 1024 / 1024
                        if gb < 1.0:
                            errors.append(f'Insufficient RAM: {gb:.2f} GB (minimum 1 GB required)')
                        else:
                            self.stdout.write(self.style.SUCCESS(f'✓ RAM: {gb:.2f} GB'))
                        break
        except Exception:
            self.stdout.write(self.style.WARNING('⚠ Could not read /proc/meminfo'))

        # certbot
        if shutil.which('certbot'):
            self.stdout.write(self.style.SUCCESS('✓ certbot found'))
        else:
            self.stdout.write(self.style.WARNING('⚠ certbot not found — SSL management will not work'))

        # Pure-FTPd
        if shutil.which('pure-ftpd'):
            self.stdout.write(self.style.SUCCESS('✓ Pure-FTPd found'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Pure-FTPd not found — install from admin panel'))

        if errors:
            self.stdout.write('')
            for e in errors:
                self.stderr.write(self.style.ERROR(f'✗ {e}'))
            sys.exit(1)
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('All requirements satisfied.'))
