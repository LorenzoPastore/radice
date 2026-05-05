#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Ensure backend/ is on sys.path so `config` and `apps` are importable
# whether invoked directly, via celery, pytest, or any other runner.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
