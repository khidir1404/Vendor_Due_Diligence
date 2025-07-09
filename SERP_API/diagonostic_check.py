#!/usr/bin/env python3
"""
Diagnostic Script for Vendor Due Diligence Application
Run this first to identify any setup issues
"""

import sys
import subprocess
import os

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Python Version Check:")
    print(f"   Python version: {sys.version}")
    if sys.version_info < (3, 7):
        print("   ❌ ERROR: Python 3.7 or higher required!")
        return False
    else:
        print("   ✅ Python version is compatible")
        return True

def check_packages():
    """Check if required packages are installed"""
    print("\n📦 Package Check:")
    required_packages = [
        'requests',
        'beautifulsoup4', 
        'python-dotenv',
        'google-search-results',
        'tenacity'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package} - installed")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
            missing_packages.append(package)

    # Check optional packages
    try:
        import customtkinter
        print("   ✅ customtkinter - installed (optional)")
    except ImportError:
        print("   ⚠️ customtkinter - not installed (will use tkinter)")

    try:
        import tkinter
        print("   ✅ tkinter - available")
    except ImportError:
        print("   ❌ tkinter - MISSING (critical error)")
        missing_packages.append('tkinter')

    return missing_packages

def check_env_file():
    """Check if .env file exists and has API key"""
    print("\n🔑 Environment File Check:")

    if not os.path.exists('.env'):
        print("   ❌ .env file not found!")
        print("   📝 Create a .env file with your SERP API key:")
        print("   SERPAPI_KEY=your_api_key_here")
        return False
    else:
        print("   ✅ .env file exists")

    try:
        with open('.env', 'r') as f:
            content = f.read()
            if 'SERPAPI_KEY' in content:
                # Check if key looks valid (not empty)
                lines = content.strip().split('\n')
                for line in lines:
                    if line.startswith('SERPAPI_KEY='):
                        key_value = line.split('=', 1)[1].strip()
                        if key_value and len(key_value) > 10:
                            print(f"   ✅ SERPAPI_KEY found (length: {len(key_value)})")
                            return True
                        else:
                            print("   ❌ SERPAPI_KEY is empty or too short")
                            return False
            else:
                print("   ❌ SERPAPI_KEY not found in .env file")
                return False
    except Exception as e:
        print(f"   ❌ Error reading .env file: {e}")
        return False

def generate_install_command(missing_packages):
    """Generate pip install command for missing packages"""
    if missing_packages:
        print("\n🔧 To fix missing packages, run:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\n   Or install all at once:")
        print("   pip install requests beautifulsoup4 python-dotenv google-search-results tenacity customtkinter")

def main():
    """Run all diagnostic checks"""
    print("🩺 VENDOR DUE DILIGENCE - DIAGNOSTIC SCRIPT")
    print("=" * 50)

    # Check Python version
    python_ok = check_python_version()

    # Check packages
    missing_packages = check_packages()

    # Check environment file
    env_ok = check_env_file()

    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY:")

    if python_ok and not missing_packages and env_ok:
        print("✅ All checks passed! Your environment should work.")
    else:
        print("❌ Issues found that need to be fixed:")
        if not python_ok:
            print("   - Python version too old")
        if missing_packages:
            print(f"   - Missing packages: {', '.join(missing_packages)}")
        if not env_ok:
            print("   - API key setup issue")

    if missing_packages:
        generate_install_command(missing_packages)

    print("\n🚀 After fixing issues, run your main application again.")

if __name__ == "__main__":
    main()
