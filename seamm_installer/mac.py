# -*- coding: utf-8 -*-
"""Mac OS specific routines handling unique operations.

* Creating the 'app'
* Installing Launch Agents to handle the Dashboard and JobServer
"""

import datetime
import getpass
import logging
import os
from pathlib import Path
import shutil
from string import Template

logger = logging.getLogger(__name__)

app_plist = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleIdentifier</key>
    <string>${identifier}</string>

    <key>CFBundleName</key>
    <string>${name}</string>

    <key>CFBundleShortVersionString</key>
    <string>${version}</string>

    <key>CFBundleExecutable</key>
    <string>${name}</string>

    <key>CFBundleIconFile</key>
    <string>${icns}</string>

    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>

    <key>LSApplicationCategoryType</key>
    <string>public.app-category.education</string>

    <key>NSHumanReadableCopyright</key>
    <string>${copyright}</string>
  </dict>
</plist>
"""  # noqa=E501

launchd_plist = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${identifier}</string>
    <key>KeepAlive</key>
    <true/>
    <key>Program</key>
    <string>${executable}</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardErrorPath</key>
    <string>${stderr_path}</string>
    <key>StandardOutPath</key>
    <string>${stdout_path}</string>
  </dict>
</plist>
"""  # noqa=E501


def create_mac_app(
    exe_path,
    identifier=None,
    name="SEAMM",
    version="0.1.0",
    user_only=False,
    icons=None,
    copyright=None,
):
    """Create an application bundle for a Mac app.

    Parameters
    ----------
    exe_path : pathlib.Path or str
        The path to the executable (required). Either a path-like object or string
    identifier : str
        The bundle identifier. If None, is set to 'org.molssi.seamm.<name>'.
    name : str
        The name of the app
    version : str = "0.1.0"
        The version of the app.
    user_only : bool = False
        Whether to install for just the current user. Defaults to all users.
    icons : pathlib.Path or string
        Optional path to the icns file to use.
    copyright : str
        The human-readable copyright. Defaults to "Copyright 2017-xxxx MolSSI"
    """
    if identifier is None:
        identifier = "org.molssi.seamm." + name

    if copyright is None:
        year = datetime.date.today().year
        copyright = f"Copyright 2017-{year} MolSSI"

    if user_only:
        applications_path = Path("~/Applications").expanduser()
    else:
        applications_path = Path("/Applications")

    contents_path = applications_path / (name + ".app") / "Contents"
    contents_path.mkdir(mode=0o755, parents=True, exist_ok=True)

    # Create the script to run the executable
    macos_path = contents_path / "MacOS"
    macos_path.mkdir(mode=0o755, parents=False, exist_ok=True)
    script_path = macos_path / name
    path = Path(exe_path).expanduser().resolve()
    script_path.write_text(f"#!/bin/bash\n{path}\n")
    script_path.chmod(0o755)

    # And put the icons in place
    resources_path = contents_path / "Resources"
    resources_path.mkdir(mode=0o755, parents=False, exist_ok=True)
    icons_path = resources_path / (name + ".icns")
    path = Path(icons).expanduser().resolve()
    shutil.copyfile(path, icons_path)

    # And the plist file itself.
    plist = Template(app_plist).substitute(
        identifier=identifier,
        name=name,
        version=version,
        icns=icons_path.name,
        copyright=copyright,
    )
    plist_path = contents_path / "Info.plist"
    plist_path.write_text(plist)


def update_mac_app(name, version):
    """Update the version for a Mac app.

    Parameters
    ----------
    name : str
        The name of the app
    version : str
        The version of the app.
    """
    for path in ("Applications", "~/Applications"):
        app_path = Path(path).expanduser() / (name + ".app") / "Contents" / "Info.plist"
        if app_path.exists():
            edited = []
            lines = iter(app_path.get_text().split_lines())
            for line in lines:
                edited.append(line)
                if "VersionString" in line:
                    edited.append(f"    <string>${version}</string>")
                    next(lines)
            app_path.write_text("\n".join(edited))


def create_mac_service(
    name,
    exe_path,
    user_agent=True,
    identifier=None,
    user_only=True,
    stderr_path=None,
    stdout_path=None,
    exist_ok=False,
):
    """Create a service on MacOS.

    The Mac supports three types of services. This function uses `user_agent` and
    `user_only` to control which is selected.

        1. A user Launch Agent for a single user, which runs while that user is logged
           in. (True, True)

        2. A Launch Agent installed by the admin that is available for all users, and
           runs when any user is logged in. (True, False)

        3. A system-wide service that runs when the machine is booted. (False, not used)


    Parameters
    ----------
    name : str
        The name of the agent
    exe_path : pathlib.Path or str
        The path to the executable (required). Either a path-like object or string
    user_agent : bool = True
        Whether to create a per-user agent (True) or system-wide daemon (False)
    identifier : str = None
        The bundle identifier. If None, is set to 'org.molssi.seamm.<name>'.
    user_only : bool = True
        Whether to install for just the current user (True) or all users (False).
        Only affects user agents, not daemons which are always system-wide.
    stderr_path : pathlib.Path or str = None
        The file to direct stderr. Defaults to "~/SEAMM/logs/<name>.out"
    stdout_path : pathlib.Path or str = None
        The file to direct stdout. Defaults to "~/SEAMM/logs/<name>.out"
    exist_ok : bool = False
        If True overwrite an existing file.
    """
    if identifier is None:
        identifier = "org.molssi.seamm." + name

    if user_agent:
        uid = os.getuid()
        if user_only:
            launchd_path = Path("~/Library/LaunchAgents").expanduser()
            plist_path = launchd_path / f"{identifier}.plist"
            text = (
                "To start the launch agent, either log out and back in, or run\n\n"
                f"   sudo launchctl bootstrap gui/{uid} {plist_path}\n\n"
                "You need administrator privileges to run this command."
            )
        else:
            launchd_path = Path("/Library/LaunchAgents")
            plist_path = launchd_path / f"{identifier}.plist"
            text = (
                "To start the launch agent, either log out and back in, or run\n\n"
                f"   sudo launchctl bootstrap user/{uid} {plist_path}\n\n"
                "You need administrator privileges to run this command."
            )
    else:
        launchd_path = Path("/Library/LaunchDaemons")
        plist_path = launchd_path / f"{identifier}.plist"
        text = (
            "To start the system-wide service, either restart the machine, or run\n\n"
            f"   sudo launchctl bootstrap system {plist_path}\n\n"
            "You need administrator privileges to run this command."
        )

    if plist_path.exists():
        if not exist_ok:
            raise FileExistsError()

    if stderr_path is None:
        stderr_path = Path(f"~/SEAMM/logs/{name}.out").expanduser()
    if stdout_path is None:
        stdout_path = Path(f"~/SEAMM/logs/{name}.out").expanduser()

    # And the plist file itself.
    plist = Template(launchd_plist).substitute(
        identifier=identifier,
        executable=str(exe_path),
        stderr_path=str(stderr_path),
        stdout_path=str(stdout_path),
    )

    # System-wide daemons need the username
    if not user_agent:
        username = getpass.getuser()
        new_plist = []
        for line in plist.splitlines():
            if "ProcessType" in line:
                new_plist.append("    <key>UserName</key>")
                new_plist.append(f"    <string>{username}</string>")
            new_plist.append(line)
        plist = "\n".join(new_plist)

    # Write the file ... we may not have permission, so catch that.
    try:
        plist_path.write_text(plist)
    except PermissionError:
        path = Path("~/Downloads").expanduser() / f"{identifier}.plist"
        path.write_text(plist)
        print(f"\nYou do not have permission to write to {launchd_path}.")
        print("If you have administrator access, run the following commands:")
        print("")
        print(f"    sudo mv {path} {plist_path}")
        print(
            "    sudo chown root:wheel /Library/LaunchDaemons/org.molssi.seamm"
            ".dashboard.plist"
        )
        print("")
        print("To move the temporary copy of the file to the correct locations.")
        print("Then start the services as follows:")
        print("")
    except Exception as e:
        print("Caught error?")
        print(e)
        print()
        raise

    print(text)
