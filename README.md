# Analyser Apps

A lightweight Windows utility for discovering, searching, and managing installed applications and games.

Analyser Apps provides a simple way to browse installed software, locate installation directories, launch applications, and access uninstallers — all from a single interface.

## Features

- **Installed Applications Scanner** — Automatically detects installed software.
- **Search** — Quickly find applications by name.
- **Steam Game Detection** — Detects installed Steam games and their installation directories.
- **Open Installation Folder** — Navigate directly to an application's directory.
- **Launch Applications** — Start applications directly from the list.
- **Uninstall Applications** — Launch the application's uninstaller.
- **Rescan** — Refresh the list of installed applications at any time.

## Preview

<!-- Add a screenshot of the application here -->

## Tech Stack

- Python
- Flet
- Windows Registry
- PyInstaller

## Requirements

- Windows 10 / 11
- 64-bit system

The standalone executable does not require Python to be installed.

## Installation

1. Go to the [Releases](../../releases) page.
2. Download the latest version.
3. Run `my_apps.exe`.
4. Wait for the application scan to complete.

## Disclaimer

Installation paths and application detection depend on how the software was installed and registered in Windows.

Launching or uninstalling applications may behave differently depending on the application itself.

Please use the uninstall feature carefully, as removing software may result in permanent data loss.

## Author

**Gradus and [Deepseek](https://chat.deepseek.com/)**

---

*Built for Windows to make installed software easier to find and manage.*
