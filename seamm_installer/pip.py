# -*- coding: utf-8 -*-
import json
import logging
import re
import subprocess

import requests

logger = logging.getLogger(__name__)

# Regular expressions for pypi query results.
SNIPPET_RE = re.compile(r"<a class=\"package-snippet\".*>")
NAME_RE = re.compile(r"<span class=\"package-snippet__name\">(.+)</span>")
VERSION_RE = re.compile(r".*<span class=\"package-snippet__version\">(.+)</span>")
DESCRIPTION_RE = re.compile(r".*<p class=\"package-snippet__description\">(.+)</p>")
NEXT_RE = re.compile(
    r'<a href="/search/.*page=(.+)" ' 'class="button button-group__button">Next</a>'
)


class Pip(object):
    """
    Class for handling pip

    Attributes
    ----------

    """

    def __init__(self):
        logger.debug("Creating Pip {str(type(self))}")

        self._base_url = "https://pypi.org/search/"

    def install(self, package):
        """Install the requested package.

        Parameters
        ----------
        package : str
            The package of interest.
        """
        command = f"pip install '{package}'"
        try:
            subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Calling pip, returncode = {e.returncode}")
            logger.warning(f"Output: {e.output}")
            raise

    def list(self, outdated=False, uptodate=False):
        """List the installed packages.

        Parameters
        ----------
        outdated: bool
            If true, list only the outdated packages. Cannot be used with
            `uptodate`.
        uptodate: bool
            If true, list only the up-to-date packages. Cannot be used with
            `outdated`.
        """
        command = "pip list"
        if outdated:
            if uptodate:
                raise ValueError("May only use one of 'outdated' and 'uptodate'.")
            command += " --outdated"
        elif uptodate:
            command += " --uptodate"
        try:
            output = subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Calling pip, returncode = {e.returncode}")
            logger.warning(f"Output: {e.output}")
            raise

        result = {}
        for line in output.splitlines():
            package, version = line.split()
            result[package] = version
        return result

    def search(self, query=None, framework=None, exact=False, progress=False):
        """Search PyPi for packages.

        Parameters
        ----------
        query : str
            The text of the query, if any.
        framework : str
            The framework classifier, if any.
        exact : bool
            Whether to only return the exact match, defaults to False.
        progress : bool
            Whether to show progress dots.

        Returns
        -------
        [str]
            A list of packages matching the query.
        """
        # Can't have exact match if no query term
        if query is None:
            exact = False

        # Set up the arguments for the http get
        args = {"q": query}
        if framework is not None:
            args["c"] = f"Framework::{framework}"

        logger.debug(f"search query: {args}")

        # PyPi serves up the results one page at a time, so loop
        if progress:
            count = 0
        result = {}
        while True:
            response = requests.get(self._base_url, params=args)
            logger.debug(f"response: {response.text}")

            snippets = SNIPPET_RE.split(response.text)

            for snippet in snippets:
                name = NAME_RE.findall(snippet)
                version = VERSION_RE.findall(snippet)
                description = DESCRIPTION_RE.findall(snippet)

                # Ignore any snippets without data, e.g. the first one.
                if len(name) > 0:
                    if not exact or name[0] == query:
                        if len(version) == 0:
                            version = "unknown"
                        else:
                            version = version[0]
                        if len(description) == 0:
                            description = "no description given"
                        else:
                            description = description[0]
                        result[name[0]] = {
                            "version": version,
                            "description": description,
                        }

                        if exact:
                            break

            if progress:
                count += 1
                if count <= 50:
                    print(".", end="")
                else:
                    count = 0
                    print("\n.", end="")
            # See if there is a next page
            next_page = NEXT_RE.findall(snippet)
            if len(next_page) == 0:
                break
            else:
                args["page"] = next_page[0]

        tmp = json.dumps(result, indent=4, sort_keys=True)
        logger.debug(f"Package information:\n{tmp}")

        return result

    def show(self, package):
        """Return the information for an installed package.

        Parameters
        ----------
        package : str
            The package of interest.
        """
        command = f"pip show '{package}'"
        try:
            result = subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            if "Package(s) not found:" in e.output:
                result = ""
            else:
                logger.warning(f"Calling pip, returncode = {e.returncode}")
                logger.warning(f"Output: {e.output}")
                raise

        data = {}
        for line in result.splitlines():
            key, value = line.split(":", maxsplit=1)
            key = key.lower()
            value = value.strip()
            if "require" in key:
                value = [x.strip() for x in value.split(",")]
            data[key] = value

        logger.debug(f"{command}\n{json.dumps(data, indent=4, sort_keys=True)}")

        return data

    def uninstall(self, package):
        """Remove the requested package.

        Parameters
        ----------
        package : str
            The package of interest.
        """
        command = f"pip uninstall --yes '{package}'"
        try:
            subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Calling pip, returncode = {e.returncode}")
            logger.warning(f"Output: {e.output}")
            raise

    def update(self, package):
        """Update the requested package.

        Parameters
        ----------
        package : str
            The package of interest.
        """
        command = f"pip install --upgrade '{package}'"
        try:
            subprocess.check_output(
                command, shell=True, text=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            line = e.output.splitlines()[-1]
            if "FileNotFoundError" in line:
                logger.warning(f"Pip returned a warning: {line}")
            else:
                logger.warning(f"Calling pip, returncode = {e.returncode}")
                logger.warning(f"Output: {e.output}")
                raise
