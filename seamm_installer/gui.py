import collections.abc
import locale
import logging
from pathlib import Path
import pkg_resources
import platform
import shutil
import sys
import tkinter as tk
import tkinter.ttk as ttk

import Pmw
import seamm_widgets as sw

from . import apps
from . import datastore
from . import my
from .util import (
    find_packages,
    get_metadata,
    package_info,
    run_plugin_installer,
)
from .services import known_services


#    set_metadata,


system = platform.system()
if system in ("Darwin",):
    from .mac import ServiceManager
    from .mac import create_app, delete_app, get_apps, update_app  # noqa: F401

    mgr = ServiceManager(prefix="org.molssi.seamm")
    icons = "SEAMM.icns"
elif system in ("Linux",):
    from .linux import ServiceManager
    from .linux import create_app, delete_app, get_apps, update_app  # noqa: F401

    mgr = ServiceManager(prefix="org.molssi.seamm")
    icons = "linux_icons"
else:
    raise NotImplementedError(f"SEAMM does not support services on {system} yet.")

logger = logging.getLogger(__name__)


# Make some styles for coloring labels
dk_green = "#008C00"
red = "#D20000"

# Help text
help_text = """\
The SEAMM installer handles installing the components of SEAMM and its plug-ins;
creating "apps", i.e. icons on your desktop or taskbar to make it easy for you to start
SEAMM; and services (or daemons) for the Dashboard and JobServer so they are always
running and ready to do your bidding.  The remaining tabs in the installer,
"Components", "Apps", and "Services" are where you go to install, update, or remove each
of these.

N.B. When you click on the component tab the installer has to examine your current
installation which takes a minute or so. The first time, and then every few days
afterwards it also has to search the Internet for all available components and
plug-ins. This takes longer, several minutes, but the data is then cached so it needn't
be done again for a few days. Be patient! And don't click on the "Components" tab if you
are only interest in the "Apps" or "Services"!


"""

class GUI(collections.abc.MutableMapping):
    def __init__(self, logger=logger):
        self.dbg_level = 30
        self.logger = logger
        self._widget = {}

        self.progress_dialog = None
        self.progress_bar = None
        self.cancel = False
        self._selected = {}
        self.packages = None
        self.package_data = {}

        self.app_data = {}
        self._selected_apps = {}

        self.service_data = {}
        self._selected_services = {}

        self.metadata = get_metadata()
        self.gui_only = self.metadata.get("gui-only", False)
        self.tabs = {}
        self.descriptions = []
        self.description_width = 0

        self.root = self.setup()

    # Provide dict like access to the widgets to make
    # the code cleaner
    def __getitem__(self, key):
        """Allow [] access to the widgets!"""
        return self._widget[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._widget[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        if key in self._widget:
            self._widget[key].destroy()
        del self._widget[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._widget)

    def __len__(self):
        """The len() command"""
        return len(self._widget)

    def event_loop(self):
        self.root.mainloop()

    def setup(self):
        locale.setlocale(locale.LC_ALL, "")

        root = tk.Tk()
        Pmw.initialise(root)

        app_name = (
            "SEAMM Installer (Development)" if my.development else "SEAMM Installer"
        )
        root.title(app_name)

        # The menus
        menu = tk.Menu(root)

        # Set the about and preferences menu items on Mac
        if sys.platform.startswith("darwin"):
            app_menu = tk.Menu(menu, name="apple")
            menu.add_cascade(menu=app_menu)

            app_menu.add_command(label="About " + app_name, command=self.about)
            app_menu.add_separator()
            root.createcommand("tk::mac::ShowPreferences", self.preferences)
            self.CmdKey = "Command-"
        else:
            self.CmdKey = "Control-"

        root.config(menu=menu)
        filemenu = tk.Menu(menu)
        debug_menu = tk.Menu(menu)
        filemenu.add_cascade(label="Debug", menu=debug_menu)
        debug_menu.add_radiobutton(
            label="normal",
            value=30,
            variable=self.dbg_level,
            command=lambda arg0=30: self.handle_dbg_level(arg0),
        )
        debug_menu.add_radiobutton(
            label="info",
            value=20,
            variable=self.dbg_level,
            command=lambda arg0=20: self.handle_dbg_level(arg0),
        )
        debug_menu.add_radiobutton(
            label="debug",
            value=10,
            variable=self.dbg_level,
            command=lambda arg0=10: self.handle_dbg_level(arg0),
        )

        # Add the notebook
        nb = self["notebook"] = ttk.Notebook(root)
        nb.grid(row=0, column=0, sticky=tk.NSEW)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        nb.bind("<<NotebookTabChanged>>", self._tab_cb)

        # Add the table for components
        page = ttk.Frame(nb)
        nb.add(page, text="Components", sticky=tk.NSEW)
        self.tabs[str(page)] = "Components"

        self["table"] = sw.ScrolledLabelFrame(page, text="SEAMM components")
        self["table"].grid(column=0, row=0, sticky=tk.NSEW)
        page.rowconfigure(0, weight=1)
        page.columnconfigure(0, weight=1)

        # and buttons below...
        frame = ttk.Frame(page)
        frame.grid(column=0, row=1)

        self["select all"] = ttk.Button(
            frame, text="Select all", command=self._select_all
        )
        self["clear selection"] = ttk.Button(
            frame, text="Clear selection", command=self._clear_selection
        )
        self["install"] = ttk.Button(
            frame, text="Install selected", command=self._install
        )
        self["uninstall"] = ttk.Button(
            frame, text="Uninstall selected", command=self._uninstall
        )
        self["update"] = ttk.Button(frame, text="Update selected", command=self._update)

        self["select all"].grid(row=0, column=0, sticky=tk.EW)
        self["clear selection"].grid(row=1, column=0, sticky=tk.EW)

        self["install"].grid(row=0, column=1, sticky=tk.EW)
        self["uninstall"].grid(row=1, column=1, sticky=tk.EW)

        self["update"].grid(row=0, column=2, sticky=tk.EW)

        # Add the apps
        page = ttk.Frame(nb)
        nb.add(page, text="Apps", sticky=tk.NSEW)
        self.tabs[str(page)] = "Apps"

        self["apps"] = sw.ScrolledLabelFrame(page, text="SEAMM apps")
        self["apps"].grid(column=0, row=0, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)

        # and buttons below...
        frame = ttk.Frame(page)
        frame.grid(column=0, row=1)

        self["create apps"] = ttk.Button(
            frame, text="Create selected apps", command=self._create_apps
        )
        self["remove apps"] = ttk.Button(
            frame, text="Remove selected apps", command=self._remove_apps
        )

        self["create apps"].grid(row=0, column=0, sticky=tk.EW)
        self["remove apps"].grid(row=0, column=1, sticky=tk.EW)

        # Add the services
        page = ttk.Frame(nb)
        nb.add(page, text="Services", sticky=tk.NSEW)
        self.tabs[str(page)] = "Services"

        self["services"] = sw.ScrolledLabelFrame(page, text="SEAMM services")
        self["services"].grid(column=0, row=0, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)

        # and buttons below...
        frame = ttk.Frame(page)
        frame.grid(column=0, row=1)

        self["create services"] = ttk.Button(
            frame, text="Create selected services", command=self._create_services
        )
        self["remove services"] = ttk.Button(
            frame, text="Remove selected services", command=self._remove_services
        )
        self["start services"] = ttk.Button(
            frame, text="Start selected services", command=self._start_services
        )
        self["stop services"] = ttk.Button(
            frame, text="Stop selected services", command=self._stop_services
        )

        self["create services"].grid(row=0, column=0, sticky=tk.EW)
        self["remove services"].grid(row=1, column=0, sticky=tk.EW)
        self["start services"].grid(row=0, column=1, sticky=tk.EW)
        self["stop services"].grid(row=1, column=1, sticky=tk.EW)

        nb.select(2)

        # Work out and set the window size to nicely fit the screen
        ws = root.winfo_screenwidth()
        hs = root.winfo_screenheight()
        w = int(0.9 * ws)
        h = int(0.8 * hs)
        x = int(0.1 * ws / 2)
        y = int(0.2 * hs / 2)

        root.geometry(f"{w}x{h}+{x}+{y}")

        self.logger.debug("Finished initializing the rest of the GUI, drawing window")
        self.logger.debug("SEAMM has been drawn. Now raise it to the top")

        # bring it to the top of all windows
        root.lift()

        # Create a progress dialog
        d = self.progress_dialog = tk.Toplevel()
        d.transient(root)

        w = self.progress_bar = ttk.Progressbar(d, orient=tk.HORIZONTAL, length=400)
        w.grid(row=0, column=0, sticky=tk.NSEW)

        w = self.progress_text = ttk.Label(d, text="Progress")
        w.grid(row=1, column=0)

        w = ttk.Button(d, text="Cancel", command=self.cancel)
        w.grid(row=2, column=0)
        w.rowconfigure(0, minsize=30)

        # Center
        w = d.winfo_reqwidth()
        h = d.winfo_reqwidth()
        x = int((ws - w) / 2)
        y = int((hs - h) / 2)

        d.geometry(f"+{x}+{y}")
        d.withdraw()

        root.update_idletasks()

        # Styles for coloring lines in table
        style = ttk.Style()
        style.configure("Green.TLabel", foreground=dk_green)
        style.configure("Red.TLabel", foreground=red)

        # root.after_idle(self.refresh)

        return root

    def cancel(self):
        print("Cancel hit!")
        self.cancel = True

    def handle_dbg_level(self, level):
        self.dbg_level = level
        logging.getLogger().setLevel(self.dbg_level)

    def about(self):
        raise NotImplementedError()

    def preferences(self):
        raise NotImplementedError()

    def refresh(self):
        """Update the table of packages."""
        self.progress_bar.configure(mode="indeterminate", value=0)
        self.progress_text.configure(
            text="Finding all packages. This may take a couple minutes."
        )
        self.progress_dialog.deiconify()
        self.root.update_idletasks()
        self.progress_bar.start()

        self.packages = find_packages(progress=True, update=self.root.update)

        self.progress_bar.stop()

        n = len(self.packages)
        self.progress_bar.configure(mode="determinate", maximum=n, value=0)
        self.progress_text.configure(
            text=f"Finding which packages are installed (0 of {n})"
        )
        self.root.update_idletasks()

        count = 0
        data = self.package_data = {}
        for package in self.packages:
            count += 1

            if package in self.packages and "description" in self.packages[package]:
                description = self.packages[package]["description"].strip()
            else:
                description = "description unavailable"

            try:
                version = my.pip.show(package)["version"]
            except Exception:
                available = self.packages[package]["version"]
                data[package] = [package, "--", available, description, "not installed"]
            else:
                available = self.packages[package]["version"]
                if version < available:
                    # See if the package has an installer
                    result = run_plugin_installer(package, "show", verbose=False)
                    if result is not None:
                        if result.returncode == 0:
                            for line in result.stdout.splitlines():
                                description += f"\n{line}"
                        else:
                            description += (
                                f"\nThe installer for {package} "
                                f"returned code {result.returncode}"
                            )
                            for line in result.stderr.splitlines():
                                description += f"\n    {line}"
                if version < available:
                    data[package] = [
                        package,
                        version,
                        available,
                        description,
                        "out of date",
                    ]
                else:
                    data[package] = [
                        package,
                        version,
                        available,
                        description,
                        "up to date",
                    ]

                self.progress_bar.step()
                self.progress_text.configure(
                    text=f"Finding which packages are installed ({count} / {n})"
                )
                self.root.update_idletasks()

        self.progress_dialog.withdraw()

    def reset_table(self):
        "Redraw the table in the GUI."

        # Sort by the plug-in names
        table = self["table"]
        frame = table.interior()

        for child in frame.grid_slaves():
            child.destroy()

        w = ttk.Label(frame, text="Version")
        w.grid(row=0, column=3, columnspan=2)

        w = ttk.Label(frame, text="Component")
        w.grid(row=1, column=1)
        w = ttk.Label(frame, text="Type")
        w.grid(row=1, column=2)
        w = ttk.Label(frame, text="Installed")
        w.grid(row=1, column=3)
        w = ttk.Label(frame, text="Available")
        w.grid(row=1, column=4)
        w = ttk.Label(frame, text="Description")
        w.grid(row=1, column=5)
        row = 2

        # Get the background color
        style = ttk.Style()
        bg = style.lookup("TLabel", "background")
        del style

        self.descriptions = []

        for ptype in ("Core package", "MolSSI plug-in", "3rd-party plug-in"):
            group = []
            for m, v, a, d, status in self.package_data.values():
                if self.packages[m]["type"] == ptype:
                    group.append([m, v, a, d, status])

            group.sort(key=lambda x: x[0])

            for m, v, a, d, status in group:
                if status == "out of date":
                    style = "Red.TLabel"
                    fg = red
                elif status == "up to date":
                    style = "Green.TLabel"
                    fg = dk_green
                else:
                    style = "TLabel"
                    fg = "black"

                if m not in self._selected:
                    self._selected[m] = tk.IntVar()
                w = ttk.Checkbutton(frame, variable=self._selected[m])
                w.grid(row=row, column=0, sticky=tk.N)
                w = ttk.Label(frame, text=m, style=style)
                w.grid(row=row, column=1, sticky="nw")
                w = ttk.Label(frame, text=str(ptype), style=style)
                w.grid(row=row, column=2, sticky=tk.N)
                w = ttk.Label(frame, text=str(v), style=style)
                w.grid(row=row, column=3, sticky=tk.N)
                w = ttk.Label(frame, text=str(a), style=style)
                w.grid(row=row, column=4, sticky=tk.N)
                w = tk.Text(frame, wrap=tk.WORD, width=50, background=bg, foreground=fg)
                w.insert("end", d.strip())
                w.grid(row=row, column=5, sticky=tk.EW)
                self.descriptions.append(w)
                row += 1

        frame.columnconfigure(5, weight=1)

        self.root.update_idletasks()

        # Set the heights of the descriptions
        self.description_width = {}
        for w in self.descriptions:
            w.bind("<Configure>", self._configure_text)
            n = w.count("1.0", "end", "displaylines")[0]
            w.configure(height=n, state=tk.DISABLED)
            self.description_width[w] = w.winfo_width()

    def _configure_text(self, event):
        w = event.widget
        width = w.winfo_width()
        if self.description_width[w] != width:
            n = w.count("1.0", "end", "displaylines")[0]
            w.configure(height=n)
            self.description_width[w] = width

    def _select_all(self):
        "Select all the packages."
        for var in self._selected.values():
            var.set(1)

    def _clear_selection(self):
        "Unselect all the packages."
        for var in self._selected.values():
            var.set(0)

    def _select_all_apps(self):
        "Select all the apps."
        for var in self._selected_apps.values():
            var.set(1)

    def _clear_apps_selection(self):
        "Unselect all the apps."
        for var in self._selected_apps.values():
            var.set(0)

    def _select_all_services(self):
        "Select all the services."
        for var in self._selected_services.values():
            var.set(1)

    def _clear_services_selection(self):
        "Unselect all the services."
        for var in self._selected_services.values():
            var.set(0)

    def _install(self):
        "Install selected packages."
        update = True
        changed = False

        n = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                available = self.packages[package]["version"]
                channel = self.packages[package]["channel"]
                installed_version, installed_channel = package_info(package)
                ptype = self.packages[package]["type"]

                if installed_channel is None:
                    n += 1
                elif update and installed_version < available:
                    n += 1

        self.progress_bar.configure(mode="determinate", maximum=n, value=0)
        self.progress_text.configure(text=f"Installing/updating packages (0 of {n})")
        self.progress_dialog.deiconify()
        self.root.update()

        count = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                available = self.packages[package]["version"]
                channel = self.packages[package]["channel"]
                installed_version, installed_channel = package_info(package)
                ptype = self.packages[package]["type"]

                if installed_channel is None:
                    print(f"Installing {ptype.lower()} {package} version {available}.")
                    if channel == "pypi":
                        my.pip.install(package)
                    else:
                        my.conda.install(package)

                    if package == "seamm-datastore":
                        datastore.update()
                    elif package == "seamm-dashboard":
                        # If installing, the service should not exist, but restart if
                        # it does.
                        service = f"dev_{package}" if my.development else package
                        mgr.restart(service, ignore_errors=True)
                    elif package == "seamm-jobserver":
                        service = f"dev_{package}" if my.development else package
                        mgr.restart(service, ignore_errors=True)
                    # See if the package has an installer
                    if not self.gui_only:
                        self.progress_text.configure(
                            text=f"Running installer for {package}"
                        )
                        self.root.update_idletasks()
                        run_plugin_installer(package, "install")

                    # Get the actual version and patch up data
                    version = my.pip.show(package)["version"]
                    self.packages[package]["version"] = version
                    m, i, a, d, status = self.package_data[package]
                    self.package_data[package] = [
                        m,
                        version,
                        version,
                        d,
                        "up to date",
                    ]
                    changed = True

                    count += 1
                    self.progress_bar.step()
                    self.progress_text.configure(
                        text=f"Installing/updating packages ({count} of {n})"
                    )
                    self.root.update_idletasks()
                elif update and installed_version < available:
                    print(
                        f"Updating {ptype.lower()} {package} from version "
                        f"{installed_version} to {available}"
                    )
                    if channel == installed_channel:
                        if channel == "pypi":
                            my.pip.install(package)
                        else:
                            my.conda.install(package)
                    else:
                        if installed_channel == "pypi":
                            my.pip.uninstall(package)
                        else:
                            my.conda.uninstall(package)
                        if channel == "pypi":
                            my.pip.install(package)
                        else:
                            my.conda.install(package)
                    # See if the package has an installer
                    if not self.gui_only:
                        self.progress_text.configure(
                            text=f"Running installer for {package}"
                        )
                        self.root.update_idletasks()
                        run_plugin_installer(package, "install")

                    # Get the actual version and patch up data
                    version = my.pip.show(package)["version"]
                    m, i, a, d, status = self.package_data[package]
                    self.package_data[package] = [
                        m,
                        version,
                        a,
                        d,
                        "up to date",
                    ]
                    changed = True

                    count += 1
                    self.progress_bar.step()
                    self.progress_text.configure(
                        text=f"Installing/updating packages ({count} of {n})"
                    )
                    self.root.update_idletasks()

        # Fix the package list
        if changed:
            self.reset_table()
        self._clear_selection()

        self.progress_dialog.withdraw()

    def _uninstall(self):
        "Uninstall selected packages."
        n = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                n += 1

        self.progress_bar.configure(mode="determinate", maximum=n, value=0)
        self.progress_text.configure(text=f"Uninstalling packages (0 of {n})")
        self.progress_dialog.deiconify()
        self.root.update_idletasks()

        changed = False
        count = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                version, channel = package_info(package)
                ptype = self.packages[package]["type"]
                print(f"Uninstalling {ptype.lower()} {package}")
                if channel == "pypi":
                    my.pip.uninstall(package)
                else:
                    my.conda.uninstall(package)
                # See if the package has an installer
                if not self.gui_only:
                    self.progress_text.configure(
                        text=f"Running uninstaller for {package}"
                    )
                    self.root.update_idletasks()
                    run_plugin_installer(package, "uninstall")

                # Patch up data
                m, i, a, d, status = self.package_data[package]
                self.package_data[package] = [m, "--", a, d, "not installed"]
                changed = True

                count += 1
                self.progress_bar.step()
                self.progress_text.configure(
                    text=f"Uninstalling packages ({count} of {n})"
                )
                self.root.update_idletasks()
        if changed:
            self.reset_table()
        self._clear_selection()

        self.progress_dialog.withdraw()

    def _update(self):
        "Update the selected packages."
        n = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                n += 1

        self.progress_bar.configure(mode="determinate", maximum=n, value=0)
        self.progress_text.configure(text=f"Updating packages (0 of {n})")
        self.progress_dialog.deiconify()
        self.root.update_idletasks()

        changed = False
        count = 0
        for package, var in self._selected.items():
            if var.get() == 1:
                available = self.packages[package]["version"]
                channel = self.packages[package]["channel"]
                installed_version, installed_channel = package_info(package)
                ptype = self.packages[package]["type"]

                if installed_version is not None and installed_version < available:
                    print(
                        f"Updating {ptype.lower()} {package} from version "
                        f"{installed_version} to {available} using {channel} "
                        f"(was installed using {installed_channel})"
                    )
                    if channel == installed_channel:
                        if channel == "pypi":
                            my.pip.update(package)
                        else:
                            my.conda.update(package)
                    else:
                        if installed_channel == "pypi":
                            my.pip.uninstall(package)
                        else:
                            my.conda.uninstall(package)
                        if channel == "pypi":
                            my.pip.install(package)
                        else:
                            my.conda.install(package)
                    # See if the package has an installer
                    if not self.gui_only:
                        self.progress_text.configure(
                            text=f"Running update for {package}"
                        )
                        self.root.update_idletasks()
                        run_plugin_installer(package, "update")

                    # Get the actual version and patch up data
                    version = my.pip.show(package)["version"]
                    m, i, a, d, status = self.package_data[package]
                    self.package_data[package] = [
                        m,
                        version,
                        version,
                        d,
                        "up to date",
                    ]
                    changed = True

                    count += 1
                    self.progress_bar.step()
                    self.progress_text.configure(
                        text=f"Updating packages ({count} of {n})"
                    )
                    self.root.update_idletasks()
        if changed:
            self.reset_table()
        self._clear_selection()

        self.progress_dialog.withdraw()

    def _create_apps(self, all_users=False):
        installed_apps = apps.get_apps()
        conda_exe = shutil.which("conda")
        conda_path = '"' + str(my.conda.path(my.environment)) + '"'
        for app_lower, var in self._selected_apps.items():
            if var.get() == 1:
                app = apps.app_names[app_lower]
                app_name = f"{app}-dev" if my.development else app
                packages = my.conda.list()
                package = apps.app_package[app_lower]
                if package in packages:
                    version = str(packages[package]["version"])
                else:
                    print(
                        f"The package '{package}' needed by the app {app_name} is not "
                        "installed."
                    )
                    continue
                if app_name in installed_apps:
                    continue

                data_path = Path(
                    pkg_resources.resource_filename("seamm_installer", "data/")
                )
                icons_path = data_path / icons
                root = "~/SEAMM_DEV" if my.development else "~/SEAMM"

                if app_lower == "dashboard":
                    bin_path = shutil.which("seamm-dashboard")
                    create_app(
                        bin_path,
                        "--root",
                        root,
                        "--port",
                        my.options.port,
                        name=app_name,
                        version=version,
                        user_only=not all_users,
                        icons=icons_path,
                    )
                elif app_lower == "jobserver":
                    bin_path = shutil.which(app.lower())
                    create_app(
                        bin_path,
                        "--root",
                        root,
                        name=app_name,
                        version=version,
                        user_only=not all_users,
                        icons=icons_path,
                    )
                else:
                    # bin_path = shutil.which(app.lower())
                    create_app(
                        conda_exe,
                        "run",
                        "-p",
                        conda_path,
                        app.lower(),
                        name=app_name,
                        version=version,
                        user_only=not all_users,
                        icons=icons_path,
                    )
                if all_users:
                    print(f"\nInstalled app {app_name} for all users.")
                else:
                    print(f"\nInstalled app {app_name} for this user.")

        self._clear_apps_selection()
        self.refresh_apps()
        self.layout_apps()

    def _remove_apps(self):
        installed_apps = apps.get_apps()
        for app_lower, var in self._selected_apps.items():
            if var.get() == 1:
                app = apps.app_names[app_lower]
                app_name = f"{app}-dev" if my.development else app
                if app_name in installed_apps:
                    delete_app(app_name, missing_ok=True)
                    print(f"Deleted the app '{app_name}'.")
                else:
                    print(f"App '{app_name}' was not installed.")
        self._clear_apps_selection()
        self.refresh_apps()
        self.layout_apps()

    def _tab_cb(self, event):
        w = self["notebook"].select()
        tab = self.tabs[w]
        if tab == "Components":
            self.refresh()
            self.reset_table()
        elif tab == "Apps":
            self.refresh_apps()
            self.layout_apps()
        elif tab == "Services":
            self.refresh_services()
            self.layout_services()

    def refresh_apps(self):
        applications = get_apps()

        data = self.app_data = {}
        for app in apps.known_apps:
            app_lower = app.lower()
            app = apps.app_names[app_lower]
            app_name = f"{app}-dev" if my.development else app
            if app_name in applications:
                path = applications[app_name]
                if path.is_relative_to(Path.home()):
                    path = path.relative_to(Path.home())
                    data[app_lower] = (app_name, "~/" + str(path))
                else:
                    data[app_lower] = (app_name, str(path))
            else:
                data[app_lower] = (app_name, "not found")

    def layout_apps(self):
        "Redraw the apps table in the GUI."

        # Sort by the plug-in names
        table = self["apps"]
        frame = table.interior()

        for child in frame.grid_slaves():
            child.destroy()

        w = ttk.Label(frame, text="Application")
        w.grid(row=0, column=1)
        w = ttk.Label(frame, text="Location")
        w.grid(row=0, column=2)
        row = 1
        for app_lower, tmp in self.app_data.items():
            app, location = tmp
            if location == "not found":
                style = "Red.TLabel"
            else:
                style = "TLabel"

            if app_lower not in self._selected_apps:
                self._selected_apps[app_lower] = tk.IntVar()
            w = ttk.Checkbutton(frame, variable=self._selected_apps[app_lower])
            w.grid(row=row, column=0, sticky=tk.N)
            w = ttk.Label(frame, text=app, style=style)
            w.grid(row=row, column=1, sticky=tk.W)
            w = ttk.Label(frame, text=location, style=style)
            w.grid(row=row, column=2, sticky=tk.W)
            row += 1

        self.root.update_idletasks()

    def refresh_services(self):
        services = mgr.list()

        print(f"{services=}")
        data = self.service_data = {}
        for service in known_services:
            service_name = f"dev_{service}" if my.development else service

            if service_name in services:
                path = Path(mgr.file_path(service_name))
                if path.is_relative_to(Path.home()):
                    path = path.relative_to(Path.home())
                    data[service] = {"path": "~/" + str(path)}
                else:
                    data[service] = {"path": str(path)}
                status = mgr.status(service_name)
                data[service]["status"] = (
                    "running" if status["running"] else "not running"
                )
                data[service]["root"] = (
                    "---" if status["root"] is None else status["root"]
                )
                data[service]["port"] = (
                    "---" if status["port"] is None else status["port"]
                )
            else:
                data[service] = {"status": "not found"}
            data[service]["name"] = service_name

    def layout_services(self):
        "Redraw the services table in the GUI."

        # Sort by the plug-in names
        table = self["services"]
        frame = table.interior()

        for child in frame.grid_slaves():
            child.destroy()

        w = ttk.Label(frame, text="Service")
        w.grid(row=0, column=1)
        w = ttk.Label(frame, text="Status")
        w.grid(row=0, column=2)
        w = ttk.Label(frame, text="Root")
        w.grid(row=0, column=3)
        w = ttk.Label(frame, text="Port")
        w.grid(row=0, column=4)
        row = 1
        for service, tmp in self.service_data.items():
            status = tmp["status"]
            if status == "not found":
                style = "Red.TLabel"
            elif status == "running":
                style = "Green.TLabel"
            else:
                style = "TLabel"

            if service not in self._selected_services:
                self._selected_services[service] = tk.IntVar()
            w = ttk.Checkbutton(frame, variable=self._selected_services[service])
            w.grid(row=row, column=0, sticky=tk.N)
            w = ttk.Label(frame, text=tmp["name"], style=style)
            w.grid(row=row, column=1, sticky=tk.W)
            w = ttk.Label(frame, text=status, style=style)
            w.grid(row=row, column=2, sticky=tk.W)
            if status != "not found":
                w = ttk.Label(frame, text=tmp["root"], style=style)
                w.grid(row=row, column=3, sticky=tk.W)
                w = ttk.Label(frame, text=tmp["port"], style=style)
                w.grid(row=row, column=4, sticky=tk.W)
            row += 1

        self.root.update_idletasks()

    def _create_services(self):
        port = 55155 if my.development else 55055
        root = "~/SEAMM_DEV" if my.development else "~/SEAMM"
        services = mgr.list()
        for service, var in self._selected_services.items():
            if var.get() == 1:
                service_name = f"dev_{service}" if my.development else service
                if service_name in services:
                    if my.options.force:
                        mgr.delete(service_name)
                    else:
                        continue
                # Proceed to creating the service.
                exe_path = shutil.which(f"seamm-{service}")
                if exe_path is None:
                    exe_path = shutil.which(service)
                if exe_path is None:
                    print(
                        f"Could not find seamm-{service} or {service}. Is it installed?"
                    )
                    print()
                    continue

                stderr_path = Path(f"{root}/logs/{service}.out").expanduser()
                stdout_path = Path(f"{root}/logs/{service}.out").expanduser()

                if service == "dashboard":
                    mgr.create(
                        service_name,
                        exe_path,
                        "--port",
                        port,
                        "--root",
                        root,
                        stderr_path=str(stderr_path),
                        stdout_path=str(stdout_path),
                    )
                else:
                    mgr.create(
                        service_name,
                        exe_path,
                        "--root",
                        root,
                        stderr_path=str(stderr_path),
                        stdout_path=str(stdout_path),
                    )
                # And start it up
                mgr.start(service_name)
                print(f"Created and started the service {service_name}")
        self._clear_services_selection()
        self.refresh_services()
        self.layout_services()

    def _remove_services(self):
        for service, var in self._selected_services.items():
            if var.get() == 1:
                service_name = f"dev_{service}" if my.development else service
                mgr.delete(service_name)
                print(f"The service {service_name} was deleted.")
        self._clear_services_selection()
        self.refresh_services()
        self.layout_services()

    def _start_services(self):
        for service, var in self._selected_services.items():
            if var.get() == 1:
                service_name = f"dev_{service}" if my.development else service
                if mgr.is_running(service_name):
                    print(f"The service '{service_name}' was already running.")
                else:
                    try:
                        mgr.start(service_name)
                    except RuntimeError as e:
                        print(e.text)
                    except NotImplementedError as e:
                        print(e.text)
                    else:
                        print(f"The service '{service_name}' has been started.")
        self._clear_services_selection()
        self.refresh_services()
        self.layout_services()

    def _stop_services(self):
        for service, var in self._selected_services.items():
            if var.get() == 1:
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
        self._clear_services_selection()
        self.refresh_services()
        self.layout_services()
