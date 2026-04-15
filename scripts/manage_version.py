#!/usr/bin/env python3
# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Version management script for AskRITA.

This script provides easy commands to bump versions using both Poetry and bump2version.
Supports semantic versioning: major.minor.patch

Usage:
    python scripts/manage_version.py --help
    python scripts/manage_version.py major    # 0.1.0 -> 1.0.0
    python scripts/manage_version.py minor    # 0.1.0 -> 0.2.0
    python scripts/manage_version.py patch    # 0.1.0 -> 0.1.1
    python scripts/manage_version.py show     # Show current version

    # Using specific version
    python scripts/manage_version.py set 1.2.3
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

_TOOL_POETRY = "poetry"
_TOOL_BUMP2VERSION = "bump2version"
_BUMP_MAJOR = "major"
_BUMP_MINOR = "minor"
_BUMP_PATCH = "patch"
_POETRY_VERSION_PREFIX = "poetry version "


def _resolve_poetry_version_cmd(cmd_args):
    """Validate and return a safe list for a 'poetry version ...' command string."""
    parts = cmd_args.split()
    if len(parts) == 3 and parts[0] == _TOOL_POETRY and parts[1] == "version":
        version_arg = parts[2]
        if version_arg in [_BUMP_MAJOR, _BUMP_MINOR, _BUMP_PATCH] or version_arg.replace(".", "").replace("-", "").isalnum():
            return [_TOOL_POETRY, "version", version_arg]
        raise ValueError(f"Invalid version argument: {version_arg}")
    raise ValueError(f"Invalid poetry command: {cmd_args}")


def _resolve_bump2version_cmd(cmd_args):
    """Validate and return a safe list for a 'bump2version ...' command string."""
    parts = cmd_args.split()
    if len(parts) == 2 and parts[0] == _TOOL_BUMP2VERSION:
        bump_type = parts[1]
        if bump_type in [_BUMP_MAJOR, _BUMP_MINOR, _BUMP_PATCH]:
            return [_TOOL_BUMP2VERSION, bump_type]
        raise ValueError(f"Invalid bump type: {bump_type}")
    raise ValueError(f"Invalid bump2version command: {cmd_args}")


def _resolve_cmd_args(cmd_args):
    """Resolve a string command to a safe list form, raising ValueError if not allowed."""
    safe_commands = {
        "poetry version --short": [_TOOL_POETRY, "version", "--short"],
        "git describe --tags --abbrev=0": ["git", "describe", "--tags", "--abbrev=0"],
        "bump2version --version": [_TOOL_BUMP2VERSION, "--version"],
    }
    if cmd_args in safe_commands:
        return safe_commands[cmd_args]
    if cmd_args.startswith(_POETRY_VERSION_PREFIX):
        return _resolve_poetry_version_cmd(cmd_args)
    if cmd_args.startswith("bump2version "):
        return _resolve_bump2version_cmd(cmd_args)
    raise ValueError(f"Command not allowed: {cmd_args}")


def _cmd_display(cmd_args):
    """Return a printable representation of cmd_args (list or string)."""
    if isinstance(cmd_args, list):
        return ' '.join(cmd_args)
    return cmd_args


def run_command(cmd_args, cwd=None):
    """Run a command safely without shell injection."""
    try:
        if isinstance(cmd_args, str):
            cmd_args = _resolve_cmd_args(cmd_args)
        result = subprocess.run(
            cmd_args, cwd=cwd or PROJECT_ROOT,
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {_cmd_display(cmd_args)}")
        print(f"   Error: {e.stderr}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Security error: {e}")
        sys.exit(1)


def get_current_version():
    """Get the current version from Poetry."""
    try:
        output = run_command("poetry version --short")
        return output.strip()
    except:
        # Fallback to reading from pyproject.toml
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        with open(pyproject_path, 'r') as f:
            for line in f:
                if line.strip().startswith('version = '):
                    return line.split('"')[1]
        return "unknown"


def show_version():
    """Display current version information."""
    current = get_current_version()
    print(f"📦 Current version: {current}")

    # Show last git tag if available
    try:
        last_tag = run_command("git describe --tags --abbrev=0")
        print(f"🏷️  Last git tag: {last_tag}")
    except:
        print("🏷️  No git tags found")


def bump_version_poetry(part):
    """Bump version using Poetry."""
    print(f"🚀 Bumping {part} version using Poetry...")
    old_version = get_current_version()

    # Poetry version bump
    run_command(f"{_POETRY_VERSION_PREFIX}{part}")
    new_version = get_current_version()

    # Update other files to match
    update_files(new_version)

    print(f"✅ Version bumped: {old_version} → {new_version}")
    return new_version


def bump_version_bump2version(part):
    """Bump version using bump2version."""
    print(f"🚀 Bumping {part} version using bump2version...")

    # Check if bump2version is available
    try:
        run_command("bump2version --version")
    except:
        print("❌ bump2version not found. Installing...")
        run_command("poetry install")

    # Run bump2version
    old_version = get_current_version()
    run_command(f"bump2version {part}")
    new_version = get_current_version()

    print(f"✅ Version bumped: {old_version} → {new_version}")
    print(f"📝 Git commit and tag created automatically")
    return new_version


def set_version(version):
    """Set a specific version."""
    print(f"🎯 Setting version to: {version}")

    old_version = get_current_version()

    # Use Poetry to set version
    run_command(f"{_POETRY_VERSION_PREFIX}{version}")

    # Update other files manually
    update_files(version)

    new_version = get_current_version()
    print(f"✅ Version set: {old_version} → {new_version}")
    print("📝 Remember to commit the changes manually")


def _update_single_file(file_info, project_root):
    """Apply a version regex replacement to one file. Returns True if the file was changed."""
    import re
    file_path = file_info['path'].resolve()
    try:
        file_path.relative_to(project_root.resolve())
    except ValueError:
        print(f"❌ Security error: File outside project root: {file_path}")
        return False
    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        return False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = re.sub(file_info['pattern'], file_info['replacement'], content)
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"📝 Updated {file_info['description']}: {file_path.name}")
            return True
        print(f"⚠️  No changes needed for {file_info['description']}: {file_path.name}")
        return False
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False


def update_files(version):
    """Update version in all tracked files."""
    import re

    # Sanitize version input - only allow semver format
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        print(f"❌ Invalid version format: {version}. Must be semantic version (e.g., 1.2.3)")
        return

    # Predefined safe file paths (no user input)
    files_to_update = [
        {
            'path': PROJECT_ROOT / "setup.py",
            'pattern': r'version="[^"]*"',
            'replacement': f'version="{version}"',
            'description': 'setup.py version'
        },
        {
            'path': PROJECT_ROOT / "askrita" / "__init__.py",
            'pattern': r'__version__ = "[^"]*"',
            'replacement': f'__version__ = "{version}"',
            'description': 'Package __init__.py version'
        }
    ]

    updated_count = sum(
        1 for file_info in files_to_update
        if _update_single_file(file_info, PROJECT_ROOT)
    )

    if updated_count > 0:
        print(f"✅ Updated {updated_count} file(s) with version {version}")
    else:
        print("ℹ️  No files needed updating")


def main():
    parser = argparse.ArgumentParser(
        description="Manage AskRITA version using Poetry and bump2version",
        epilog="""
Examples:
  %(prog)s show          # Show current version
  %(prog)s major         # Bump major version (0.1.0 -> 1.0.0)
  %(prog)s minor         # Bump minor version (0.1.0 -> 0.2.0)
  %(prog)s patch         # Bump patch version (0.1.0 -> 0.1.1)
  %(prog)s set 1.2.3     # Set specific version
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'action',
        choices=['show', _BUMP_MAJOR, _BUMP_MINOR, _BUMP_PATCH, 'set'],
        help='Version action to perform'
    )

    parser.add_argument(
        'version',
        nargs='?',
        help='Specific version to set (only for "set" action)'
    )

    parser.add_argument(
        '--tool',
        choices=[_TOOL_POETRY, _TOOL_BUMP2VERSION],
        default=_TOOL_POETRY,
        help='Tool to use for version bumping (default: poetry)'
    )

    parser.add_argument(
        '--no-commit',
        action='store_true',
        help='Skip git commit when using bump2version'
    )

    args = parser.parse_args()

    # Change to project root
    print(f"📁 Working in: {PROJECT_ROOT}")

    if args.action == 'show':
        show_version()
    elif args.action == 'set':
        if not args.version:
            print("❌ Version required for 'set' action")
            sys.exit(1)
        set_version(args.version)
    elif args.action in [_BUMP_MAJOR, _BUMP_MINOR, _BUMP_PATCH]:
        if args.tool == _TOOL_POETRY:
            bump_version_poetry(args.action)
        else:
            bump_version_bump2version(args.action)

        print("\n🎉 Version bump complete!")
        print("\n📋 Next steps:")
        if args.tool == _TOOL_POETRY:
            print("   1. Review changes: git diff")
            print("   2. Commit changes: git add . && git commit -m 'Bump version'")
            print("   3. Create tag: git tag v$(poetry version --short)")
            print("   4. Push: git push && git push --tags")
        else:
            print("   1. Review changes: git log --oneline -n 2")
            print("   2. Push: git push && git push --tags")
        print("   3. Build: poetry build")
        print("   4. Publish: poetry publish")


if __name__ == "__main__":
    main()
