# -*- coding: utf-8 -*-
"""Linux OS specific routines handling unique operations.

* Installing daemons to handle the Dashboard and JobServer
"""

import getpass
import logging
from pathlib import Path
from string import Template
import subprocess

logger = logging.getLogger(__name__)

user_text = """\
[Unit]
Description=${description}
[Service]
WorkingDirectory=${wd}
ExecStart=${exe}
Type=simple
TimeoutStopSec=10
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
"""

service_text = """\
[Unit]
Description=${description}
[Service]
User=${username}
WorkingDirectory=${wd}
ExecStart=${exe}
Type=simple
TimeoutStopSec=10
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
"""


def create_linux_service(
    name,
    exe_path,
    description=None,
    user_agent=True,
    user_only=True,
    exist_ok=False,
):
    """Create a service on Linux

    Linux supports three types of services. This function uses `user_agent` and
    `user_only` to control which is selected.

        1. A user service for a single user, which runs while that user is logged
           in. (True, True)

        2. A service installed by the admin that is available for all users, and
           runs when any user is logged in. (True, False)

        3. A system-wide service (daemon) that runs when the machine is booted.
           (False, not used)

    Parameters
    ----------
    name : str
        The name of the agent
    exe_path : pathlib.Path or str
        The path to the executable (required). Either a path-like object or string
    description : str = None
        The description of the service. Default is to generate from the name.
    user_agent : bool = True
        Whether to create a per-user agent (True) or system-wide daemon (False)
    user_only : bool = True
        Whether to install for just the current user (True) or all users (False).
        Only affects user agents, not daemons which are always system-wide.
    exist_ok : bool = False
        If True overwrite an existing file.
    """
    if user_agent:
        if user_only:
            systemd_path = Path("~/.config/systemd/user").expanduser()
            service_path = systemd_path / f"{name}.service"
            cmd = f"systemctl --user --now enable {service_path}"
            text = (
                "To start the launch agent, either log out and back in, or run\n\n"
                f"   sudo {cmd}\n\n"
                "You need administrator privileges to run this command."
            )
        else:
            systemd_path = Path("/etc/systemd/user")
            service_path = systemd_path / f"{name}.service"
            cmd = f"systemctl --now enable {service_path}"
            text = (
                "To start the launch agent, either log out and back in, or run\n\n"
                f"   sudo {cmd}\n\n"
                "You need administrator privileges to run this command."
            )
    else:
        systemd_path = Path("/etc/systemd/system")
        service_path = systemd_path / f"{name}.service"
        cmd = f"systemctl --now enable {service_path}"
        text = (
            "To start the system-wide service, either restart the machine, or run\n\n"
            f"   sudo {cmd}\n\n"
            "You need administrator privileges to run this command."
        )

    if description is None:
        description = name.replace("-", " ").title().replace("Seamm", "SEAMM")

    if service_path.exists():
        if not exist_ok:
            raise FileExistsError()

    wd_path = Path("~/SEAMM/services").expanduser()
    wd_path.mkdir(mode=0o755, parents=True, exist_ok=True)
    script_path = wd_path / name

    # Create the script for running the service
    script_path.write_text(f"#!/bin/bash\n{exe_path}")
    script_path.chmod(0o755)

    # And the service file itself.
    if user_agent:
        service = Template(user_text).substitute(
            description=description,
            wd=str(wd_path),
            exe=str(script_path),
        )
    else:
        # System-wide daemons need the username
        username = getpass.getuser()
        service = Template(user_text).substitute(
            description=description,
            user=username,
            wd=str(wd_path),
            exe=str(script_path),
        )

    # Write the file ... we may not have permission, so catch that.
    try:
        service_path.write_text(service)
        print(f"Wrote the systemd file to {service_path}.")
    except PermissionError:
        downloads = Path("~/Downloads").expanduser()
        downloads.mkdir(exist_ok=True)
        path = downloads / f"{name}.service"
        path.write_text(service)
        print(f"\nYou do not have permission to write to {systemd_path}.")
        print("If you have administrator access, run the following commands:")
        print("")
        print(f"    sudo mv {path} {service_path}")
        print(f"    sudo chown root:root {service_path}")
        print("")
        print("To move the temporary copy of the file to the correct locations.")
        print("Then start the services as follows:")
        print("")
        print(text)
    except Exception as e:
        print("Caught error?")
        print(e)
        print()
        raise

    # And start it...
    try:
        result = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Caught exception {e}")
        print(text)
    except Exception as e:
        print(f"Caught unknown exception {e}")
        print(text)
