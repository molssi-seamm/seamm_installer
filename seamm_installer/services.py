# -*- coding: utf-8 -*-

"""Handle the services (daemons) for SEAMM."""

from pathlib import Path
import platform
import shutil

from tabulate import tabulate

from . import my


system = platform.system()
if system in ("Darwin",):
    from .mac import ServiceManager

    mgr = ServiceManager(prefix="org.molssi.seamm")
elif system in ("Linux",):
    from .linux import ServiceManager

    mgr = ServiceManager(prefix="org.molssi.seamm")
else:
    raise NotImplementedError(f"SEAMM does not support services on {system} yet.")

known_services = ["dashboard", "jobserver"]


def setup(parser):
    """Define the command-line interface for handling services.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The main parser for the application.
    """
    services_parser = parser.add_parser("services")
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
        default=55155 if my.development else 55055,
    )
    host = platform.node()
    if host == "":
        host = "unknown"
    tmp_parser.add_argument(
        "--dashboard-name",
        default=f"{host} Development" if my.development else host,
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
        help="The services to delete: %(default)s",
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
    tmp_parser = subparser.add_parser("restart")
    tmp_parser.set_defaults(func=start)
    tmp_parser.add_argument(
        "services",
        nargs="*",
        default=known_services,
        help="The services to restart: %(default)s",
    )

    # Show
    tmp_parser = subparser.add_parser("show")
    tmp_parser.set_defaults(func=show)
    tmp_parser.add_argument(
        "--all",
        action="store_true",
        help="Show both the normal and development services.",
    )
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
    services = mgr.list()
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        if service_name in services:
            if my.options.force:
                mgr.delete(service_name)
            else:
                print(
                    f"The service '{service_name}' already exists! Use --force to "
                    "recreate the service from scratch."
                )
                continue
        # Proceed to creating the service.
        exe_path = shutil.which(f"seamm-{service}")
        if exe_path is None:
            exe_path = shutil.which(service)
        if exe_path is None:
            print(f"Could not find seamm-{service} or {service}. Is it installed?")
            print()
            continue

        root = "~/SEAMM_DEV" if my.development else "~/SEAMM"
        stderr_path = Path(f"{my.options.root}/logs/{service}.out").expanduser()
        stdout_path = Path(f"{my.options.root}/logs/{service}.out").expanduser()

        if service == "dashboard":
            mgr.create(
                service_name,
                exe_path,
                "--root",
                root,
                "--port",
                my.options.port,
                "--dashboard-name",
                my.options.dashboard_name,
                stderr_path=str(stderr_path),
                stdout_path=str(stdout_path),
            )
        else:
            mgr.create(
                service_name,
                exe_path,
                "--root",
                root,
                "JobServer",
                "--no-windows",
                stderr_path=str(stderr_path),
                stdout_path=str(stdout_path),
            )
        # And start it up
        mgr.start(service_name)
        print(f"Created and started the service {service_name}")


def delete():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        mgr.delete(service_name)
        print(f"The service {service_name} was deleted.")


def restart():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        try:
            mgr.restart(service_name)
        except RuntimeError as e:
            print(e.text)
        except NotImplementedError as e:
            print(e.text)
        else:
            print(f"The service '{service_name}' was restarted.")


def show():
    services = mgr.list()
    table = []
    for development in [False, True] if my.options.all else [my.development]:
        for service in my.options.services:
            service_name = f"dev_{service}" if development else service
            if service_name in services:
                path = mgr.file_path(service_name)
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


def start():
    for service in my.options.services:
        service = f"dev_{service}" if my.development else service
        if mgr.is_running(service):
            print(f"The service '{service}' was already running.")
        else:
            try:
                mgr.start(service)
            except RuntimeError as e:
                print(e.text)
            except NotImplementedError as e:
                print(e.text)
            else:
                print(f"The service '{service}' has been started.")


def status():
    services = mgr.list()
    table = []
    for development in [False, True] if my.options.all else [my.development]:
        for service in my.options.services:
            service = f"dev_{service}" if development else service
            if service in services:
                status = mgr.status(service)
                row = [
                    service,
                    "running" if status["running"] else "not running",
                    "---" if status["root"] is None else status["root"],
                    "---" if status["port"] is None else status["port"],
                    (
                        "---"
                        if status["dashboard name"] is None
                        else status["dashboard name"]
                    ),
                ]
            else:
                row = [service, "not created"]
            table.append(row)
    print(
        tabulate(
            table,
            ("Service", "Status", "Root", "Port", "Name"),
            tablefmt="fancy_grid",
        )
    )


def stop():
    for service in my.options.services:
        service_name = f"dev_{service}" if my.development else service
        if mgr.is_running(service_name):
            try:
                mgr.stop(service_name)
            except RuntimeError as e:
                print(e.text)
            except NotImplementedError as e:
                print(e.text)
            else:
                print(f"The service '{service_name}' has been stopped.")
        else:
            print(f"The service '{service_name}' was not running.")
