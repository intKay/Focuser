# Install Focuser

## Recommended: source bundle, one installer

1. Install Python 3.10+ from your OS package manager or python.org. On Fedora: `sudo dnf install python3 python3-pip`. Windows Python should include Tcl/Tk and be available as `python` in a terminal.
2. Download `focuser-local-1.3.0rc2-source.zip` from [v1.3.0-rc.2](https://github.com/intKay/Focuser/releases/tag/v1.3.0-rc.2), extract to a permanent writable folder and open a terminal there.
3. First-time users run `python install.py --new-install` on Windows, or `python3 install.py --new-install` on Linux/macOS. Use a normal user account. No administrator rights are needed for Focuser.

The installer creates `.venv`, installs dependencies, prepares a Chromium extension folder and configures startup at user login. It opens `http://127.0.0.1:18765/`. Dependency installation needs network access; normal runtime does not.

Use `--plan` to preview without writes, `--no-open` to keep the browser closed, or `--no-startup` to generate startup templates without enabling them. Linux login startup requires a systemd user session. The installer does not install Python, sign extensions or install browser extensions automatically.

## Connect the extension

In **Connect & settings**, download `chromium.zip` and extract it to a permanent folder. Open your browser's extension manager:

| Browser | Address |
| --- | --- |
| Chrome / Brave / Chromium | `chrome://extensions` |
| Edge | `edge://extensions` |
| Vivaldi | `vivaldi://extensions` |
| Opera | `opera://extensions` |

Enable **Developer mode**, click **Load unpacked** and choose the folder containing `manifest.json`. Install in every browser and connect all to the same service/port. Refresh target websites after installation or upgrades. Private windows need their own extension permission.

Firefox: extract the Firefox asset, open `about:debugging#/runtime/this-firefox`, choose **Load Temporary Add-on**, then select `manifest.json`. This is an unsigned test extension; it is removed after a browser restart.

## Existing users: never reset your allowance

Back up the complete original private data directory. Run the installer with `--data-dir /absolute/path/to/existing-data` and omit `--new-install`. Windows uses `python`; Linux/macOS use `python3`. A custom port is passed with `--port`. Keep the same interpreter, startup settings and data path on upgrades; conflicting startup entries are refused.

The installer does not stop an existing backend or edit state. A running backend may continue using the previous loaded code until a maintenance restart. Test upgrades in isolated data/ports first, then stop the original process for maintenance and immediately restart with the original data and port. Do not use this interruption to restore access.

Cross-system migration: copy final private data after stopping the original backend. Never upload it to GitHub. Unsupported active Windows app rules must be adjusted through the original dashboard's verification flow before Linux/macOS migration. Full [Fedora migration instructions](fedora.md). New target-system extensions bind to the migrated directory, not an empty replacement.

Default new-user data: Windows `%LOCALAPPDATA%\Focuser`; macOS `~/Library/Application Support/Focuser`; Linux `${XDG_DATA_HOME:-~/.local/share}/focuser`. Older source installs may use `outputs/screen_time/release/ScreenTime/data`; use the actual existing directory.

## Wheel / advanced installation

The wheel is a Python package, not a standalone executable. In a virtual environment install `focuser_local-1.3.0rc2-py3-none-any.whl`. Windows native app limits additionally need `psutil`, `pystray`, `Pillow` and the Python distribution's Tk component; use the source installer for an automatic dependency setup.

```sh
focuser setup --new-install --enable-startup
# Existing users:
focuser setup --data-dir /path/to/existing-data --enable-startup
focuser --data-dir /path/to/existing-data --background
```

The web and extension language selectors store UI preferences only. Native Windows prompts follow system locale; `focuser --lang en` or `FOCUSER_LANG=en` forces English. Custom category names remain user content and are not rewritten by translation.

## If something goes wrong

- No dashboard: check `http://127.0.0.1:18765/api/health`. On Linux use `systemctl --user status focuser.service` and `journalctl --user -u focuser.service`.
- Different data binding: start the original directory, or connect a new target-system extension to the privately migrated directory. Never create new usage data to repair a connection.
- Native rules unsupported: Windows needs desktop dependencies; Linux/macOS currently enforce websites only.
- Existing startup entry conflicts: keep its original paths and port. The installer refuses to overwrite it.
- Share only sanitized errors, version and reproduction steps. Do not upload state, logs containing private paths or browser profiles.
