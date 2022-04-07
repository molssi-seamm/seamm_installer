# -*- coding: utf-8 -*-

"""Handle the services (daemons) for SEAMM."""

import os
from pathlib import Path
import platform
import re
import shutil
from string import Template
import subprocess

from tabulate import tabulate

from . import my

known_services = ["dashboard", "jobserver"]

plist = {}

plist[
    "dashboard"
] = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>org.molssi.seamm.${service}</string>
    <key>KeepAlive</key>
    <true/>
    <key>ProgramArguments</key>
    <array>
       <string>${executable}</string>
       <string>--port</string>
       <string>${port}</string>
       <string>--root</string>
       <string>${root}</string>
    </array>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardErrorPath</key>
    <string>${stderr_path}</string>
    <key>StandardOutPath</key>
    <string>${stdout_path}</string>
  </dict>
</plist>
"""  # noqa=E501

plist[
    "jobserver"
] = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>org.molssi.seamm.${service}</string>
    <key>KeepAlive</key>
    <true/>
    <key>ProgramArguments</key>
    <array>
       <string>${executable}</string>
       <string>--root</string>
       <string>${root}</string>
    </array>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardErrorPath</key>
    <string>${stderr_path}</string>
    <key>StandardOutPath</key>
    <string>${stdout_path}</string>
  </dict>
</plist>
"""  # noqa=E501


def setup(parser):
    """Define the command-line interface for handling services.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The main parser for the application.
    """
    services_parser = parser.add_parser("service")
    subparser = services_parser.add_subparsers()

    # Create
    tmp_parser = subparser.add_parser("create")
    tmp_parser.set_defaults(func=create)
    tmp_parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate the service if it already exists.",
    )
    tmp_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=55066 if my.development else 55055,
    )
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to create: %(default)s",
    )

    # Delete
    tmp_parser = subparser.add_parser("delete")
    tmp_parser.set_defaults(func=delete)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to create: %(default)s",
    )

    # Start
    tmp_parser = subparser.add_parser("start")
    tmp_parser.set_defaults(func=start)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to start: %(default)s",
    )

    # Stop
    tmp_parser = subparser.add_parser("stop")
    tmp_parser.set_defaults(func=stop)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to stop: %(default)s",
    )

    # restart
    tmp_parser = subparser.add_parser("start")
    tmp_parser.set_defaults(func=start)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to start: %(default)s",
    )

    # Show
    tmp_parser = subparser.add_parser("show")
    tmp_parser.set_defaults(func=show)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to show: %(default)s",
    )

    # Status
    tmp_parser = subparser.add_parser("status")
    tmp_parser.set_defaults(func=status)
    tmp_parser.add_argument(
        "--all",
        action="store_true",
        help="Show the status of both normal and development services.",
    )
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to show: %(default)s",
    )


def create():
    system = platform.system()
    identifier = "org.molssi.seamm"

    if system in ("Darwin",):
        agent = mac_get_agents()
        for service in my.options.services:
            service_name = f"dev_{service}" if my.development else service
            if service_name in agent:
                if not my.options.force:
                    print(
                        f"The service '{service_name}' already exists! Use --force to "
                        "recreate the service from scratch."
                    )
                    continue
                domain, service_target, path = agent[service_name]
                # Check if it is running
                cmd = f"launchctl print {service_target}"
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                if result.returncode == 0:
                    # Yes, so stop it
                    cmd = f"launchctl bootout {service_target}"
                    result = subprocess.run(
                        cmd, shell=True, text=True, capture_output=True
                    )
                    if result.returncode == 0:
                        pass
                    else:
                        print(f"Could not stop the service '{service_name}':")
                        print(result.stderr)
                        continue
                # Now remove the files
                path.unlink(missing_ok=True)

            # Proceed to creating the service.
            uid = os.getuid()
            domain = f"gui/{uid}"
            launchd_path = Path("~/Library/LaunchAgents").expanduser()
            path = launchd_path / f"{identifier}.{service_name}.plist"
            text = (
                "To start the launch agent, either log out and back in, or "
                f"run\n\n   launchctl bootstrap gui/{uid} {path}"
            )

            if path.exists() and not my.options.force:
                print(f"The service file {path} exists! Use --force to overwrite")
                continue

            exe_path = shutil.which(f"seamm-{service}")
            if exe_path is None:
                exe_path = shutil.which(service)
            if exe_path is None:
                print(f"Could not find seamm-{service} or {service}. Is it installed?")
                print()
                continue

            stderr_path = Path(f"{my.options.root}/logs/{service}.out").expanduser()
            stdout_path = Path(f"{my.options.root}/logs/{service}.out").expanduser()

            # And the plist file itself.
            content = Template(plist[service]).substitute(
                service=service_name,
                executable=str(exe_path),
                port=str(my.options.port),
                root=my.options.root,
                stderr_path=str(stderr_path),
                stdout_path=str(stdout_path),
            )

            # Write the file ... we may not have permission, so catch that.
            try:
                path.write_text(content)
            except PermissionError:
                tmp_path = Path("~/Downloads").expanduser() / f"{identifier}.plist"
                tmp_path.write_text(content)
                print(f"\nYou do not have permission to write to {path}.")
                print("The needed file has been written to ~/Downloads")
                print("If you can move it to the correct place, do so")
                print("then start the services as follows:")
                print("")
                print(text)
            except Exception as e:
                print("Caught error?")
                print(e)
                print()
                raise

            # And start it up
            print(f"Starting the service {service_name}")
            cmd = f"launchctl bootstrap {domain} {path}"
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            if result.returncode == 0:
                pass
            else:
                print(f"Starting the service '{service}' was not successful:")
                print(result.stderr)
    elif system in ("Linux",):
        print("Linux not implemented yet.")
    else:
        print(f"SEAMM does not support services on {system} yet.")


def delete():
    system = platform.system()
    identifier = "org.molssi.seamm"

    if system in ("Darwin",):
        agent = mac_get_agents()
        for service in my.options.services:
            service_name = f"dev_{service}" if my.development else service
            if service_name in agent:
                domain, service_target, path = agent[service_name]
                # Check if it is running
                cmd = f"launchctl print {service_target}"
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                if result.returncode == 0:
                    # Yes, so stop it
                    cmd = f"launchctl bootout {service_target}"
                    result = subprocess.run(
                        cmd, shell=True, text=True, capture_output=True
                    )
                    if result.returncode == 0:
                        pass
                    else:
                        print(f"Could not stop the service '{service_name}':")
                        print(result.stderr)
                        continue
                # Now remove the files
                path.unlink(missing_ok=True)
            else:
                # Check if the plist file exists, and remove if it does.
                launchd_path = Path("~/Library/LaunchAgents").expanduser()
                path = launchd_path / f"{identifier}.{service_name}.plist"
                path.unlink(missing_ok=True)
            print(f"Deleted the service '{service}'.")
    elif system in ("Linux",):
        print("Linux not implemented yet.")
    else:
        print(f"SEAMM does not support services on {system} yet.")


def is_running(service_name):
    system = platform.system()

    result = False
    if system in ("Darwin",):
        agent = mac_get_agents()
        if service_name in agent:
            service_target = agent[service_name][1]
            cmd = f"launchctl print {service_target}"

            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)

            if result.returncode == 0:
                result = True
            else:
                result = False
        else:
            result = False
    elif system in ("Linux",):
        raise NotImplementedError("Linux not implemented yet.")
    else:
        raise NotImplementedError(f"SEAMM does not support services on {system} yet.")

    return result


def mac_get_agents():
    identifier = "org.molssi.seamm."
    uid = os.getuid()

    paths = (
        (Path("~/Library/LaunchAgents").expanduser(), f"gui/{uid}"),
        (Path("/Library/LaunchAgents"), f"gui/{uid}"),
        (Path("/Library/LaunchDaemons"), "system"),
    )
    agent = {}
    pattern = identifier + "*"
    for path, domain in paths:
        for file_path in path.glob(pattern):
            service_name = file_path.stem
            service_target = f"{domain}/{service_name}"
            short_name = file_path.suffixes[-2][1:]
            agent[short_name] = (domain, service_target, file_path)
    return agent


def restart():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        try:
            restart_service(service_name)
        except RuntimeError as e:
            print(e.text)
        except NotImplementedError as e:
            print(e.text)
        else:
            print(f"The service '{service_name}' was restarted.")


def restart_service(service_name):
    stop_service(service_name)
    start_service(service_name)


def show():
    system = platform.system()

    if system in ("Darwin",):
        agent = mac_get_agents()

        table = []
        for service in my.options.services:
            service_name = f"dev_{service}" if my.development else service
            if service_name in agent:
                path = agent[service_name][2]
                if path.is_relative_to(Path.home()):
                    path = path.relative_to(Path.home())
                    table.append((service_name, "~/" + str(path)))
                else:
                    table.append((service_name, str(path)))
            else:
                table.append((service_name, "not found"))
        if len(table) == 0:
            print("Found no services.")
        else:
            print(tabulate(table, ("Service", "Path"), tablefmt="fancy_grid"))
    elif system in ("Linux",):
        print("Linux not implemented yet.")
    else:
        print(f"SEAMM does not support services on {system} yet.")


def start():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        if is_running(service_name):
            print(f"The service '{service_name}' was already running.")
        else:
            try:
                start_service(service_name)
            except RuntimeError as e:
                print(e.text)
            except NotImplementedError as e:
                print(e.text)
            else:
                print(f"The service '{service_name}' has been started.")


def start_service(service_name):
    system = platform.system()

    result = False
    if system in ("Darwin",):
        if is_running(service_name):
            result = True
        else:
            agent = mac_get_agents()
            if service_name in agent:
                domain, service_target, path = agent[service_name]

                cmd = f"launchctl bootstrap {domain} {path}"
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                if result.returncode == 0:
                    result = True
                else:
                    raise RuntimeError(
                        f"Starting the service '{service_name}' was not successful:\n"
                        f"{result.stderr}"
                    )
    elif system in ("Linux",):
        raise NotImplementedError("Linux not implemented yet.")
    else:
        raise NotImplementedError(f"SEAMM does not support services on {system} yet.")

    return result


def status():
    system = platform.system()

    if system in ("Darwin",):
        agent = mac_get_agents()
        table = []
        for development in [False, True] if my.options.all else [my.development]:
            for service in my.options.services:
                service_name = f"dev_{service}" if development else service
                if service_name in agent:
                    service_target = agent[service_name][1]
                    cmd = f"launchctl print {service_target}"

                    result = subprocess.run(
                        cmd, shell=True, text=True, capture_output=True
                    )

                    row = [service_name]

                    if result.returncode == 0:
                        row.append("running")
                    else:
                        row.append("not running")

                    # Get the root directory and, for the dashboard, port
                    path = agent[service_name][2]
                    root = None
                    port = None
                    my.logger.debug(f"Checking {path} for the root and port")
                    lines = iter(path.read_text().splitlines())
                    for line in lines:
                        if "--root" in line:
                            line = next(lines)
                            match = re.search("<string>(.+)</string>", line)
                            root = None if match is None else match.group(1)
                        if "--port" in line:
                            line = next(lines)
                            match = re.search("<string>(.+)</string>", line)
                            port = None if match is None else match.group(1)
                    row.append("?" if root is None else root)
                    if port is not None:
                        row.append(port)
                else:
                    row.append("not created")
                    print(f"The service '{service_name}' has not been created.")

                table.append(row)
        print(
            tabulate(
                table, ("Service", "Status", "Root", "Port"), tablefmt="fancy_grid"
            )
        )

    elif system in ("Linux",):
        print("Linux not implemented yet.")
    else:
        print(f"SEAMM does not support services on {system} yet.")


def stop():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        if is_running(service_name):
            try:
                stop_service(service_name)
            except RuntimeError as e:
                print(e.text)
            except NotImplementedError as e:
                print(e.text)
            else:
                print(f"The service '{service_name}' has been stopped.")
        else:
            print(f"The service '{service_name}' was not running.")


def stop_service(service_name):
    system = platform.system()

    result = False
    if system in ("Darwin",):
        if is_running(service_name):
            agent = mac_get_agents()
            domain, service_target, path = agent[service_name]

            cmd = f"launchctl bootout {service_target}"
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            if result.returncode == 0:
                result = True
            else:
                raise RuntimeError(
                    f"Stopping the service '{service_name}' was not successful:\n"
                    f"{result.stderr}"
                )
        else:
            return True
    elif system in ("Linux",):
        raise NotImplementedError("Linux not implemented yet.")
    else:
        raise NotImplementedError(f"SEAMM does not support services on {system} yet.")
