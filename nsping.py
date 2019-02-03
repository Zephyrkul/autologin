from __future__ import print_function
import os
import sys
import logging
import logging.handlers
from getpass import getpass
import json
import random
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from xml.etree import ElementTree
from xml.dom import minidom

logger = logging.getLogger(__name__)
log_fmt = logging.Formatter(
    "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
    datefmt="[%d/%m/%Y %H:%M]",
)
fhandler = logging.handlers.RotatingFileHandler(
    filename="errors.log", encoding="utf-8", mode="a", maxBytes=8000000, backupCount=5
)
fhandler.setFormatter(log_fmt)
logger.addHandler(fhandler)


rate_limit_buffer = 10


old_filename = os.path.splitext(os.path.basename(__file__))[0] + ".json"
defaultagent = "%s (Darcania's autologin script)"


def static_vars(**kwargs):
    def decorate(func):
        for k, v in kwargs.items():
            setattr(func, k, v)
        return func

    return decorate


def clear():
    return os.system("cls" if os.name == "nt" else "clear")


def main():
    try:
        with open(old_filename, mode="r", encoding="utf-8") as jsonfile:
            nations = json.load(jsonfile)
            nations.pop("AGENT", None)
            with open(".tokens", mode="w", encoding="utf-8") as tokenfile:
                for tup in nations.items():
                    tokenfile.write("%s:%s\n" % tup)
        os.remove(old_filename)
    except FileNotFoundError:
        pass

    while True:
        clear()
        print("Darcania's autologin script\n")
        for i, options in enumerate(main_menu_options, 1):
            _, text = options  # unpack the tuple
            print("  %d. %s" % (i, text))
        print("\n  0. Exit\n")
        while True:
            response = input("> ")
            try:
                response = int(response)
            except ValueError:
                print("%r doesn't look like a number, could you try again?" % response)
                continue
            if response == 0:
                sys.exit(0)
            try:
                function = main_menu_options[response - 1][0]
            except IndexError:
                print("%d isn't a valid option, could you try again?" % response)
                continue
            break
        print()
        function()


def run():
    try:
        with open("settings.json", "r", encoding="utf-8") as settings:
            agent = defaultagent % json.load(settings)["agent"]
    except (FileNotFoundError, json.JSONDecodeError):
        input("User agent not set. Press enter to return to the menu . . . ")
        return
    try:
        with open(".tokens", mode="r", encoding="utf-8") as tokens:
            for line in tokens:
                nation, autologin = tuple(map(str.strip, line.split(":")))
                try:
                    _log(agent, nation, autologin=autologin)
                except HTTPError as error:
                    if error.code == 403:
                        logger.error("%s's password is incorrect. Please update it.", nation)
                    elif error.code == 404:
                        logger.error(
                            "%s does not exist. Please revive it or update your nation list.",
                            nation,
                        )
                    elif error.code == 409:
                        logger.info("%s was logged into too recently, so it was skipped.", nation)
                    elif error.code == 429:
                        print(
                            "The rate limit was exceeded and you've been locked out. Aborting run."
                        )
                        input("Press enter to return to the menu . . . ")
                        return
                    elif error.code >= 500:
                        print("An internal server error occurred. Aborting run.")
                        input("Press enter to return to the menu . . . ")
                        return
                    else:
                        logger.error(error)
                        print("An unknown error occurred. Aborting run.")
                        input("Press enter to return to the menu . . . ")
                        return
                except Exception as error:
                    logger.exception(error)
                    print(
                        "Something went wrong with the script. Please contact Darcania with the above traceback at your earliest convenience. Aborting run."
                    )
                    input("Press enter to return to the menu . . . ")
                    return
        input("Run complete. Press enter to return to the menu . . . ")
    except FileNotFoundError:
        input("No nations have been saved. Press enter to return to the menu . . . ")


def set_agent():
    print(
        "Set a new user agent. Be sure to keep it descriptive, e.g. nation name and contact email."
    )
    print("The script itself will append information about itself automatically.")
    agent = input("New agent: ")
    if not agent:
        input("No agent given. Press enter to return to the menu . . . ")
    with open("settings.json", "w", encoding="utf-8") as settings:
        json.dump({"agent": agent}, settings)

    input("User agent set. Press enter to return to the menu . . . ")


def add_nations():
    try:
        with open("settings.json", "r", encoding="utf-8") as settings:
            agent = defaultagent % json.load(settings)["agent"]
    except (FileNotFoundError, json.JSONDecodeError):
        input("User agent not set. Press enter to return to the menu . . . ")
        return
    to_add = {}
    while True:
        nation = input("Nation: ")
        if not nation:
            break
        nation = "_".join(nation.strip().lower().split())
        if any(c not in "-0123456789_abcdefghijklmnopqrstuvwxyz" for c in nation):
            print("Invalid nation name.")
            continue
        password = getpass()
        while not password:
            print("No password entered. Please provide a password.")
            password = getpass()
        print("Fetching nation token from NS, please wait . . . ")
        try:
            data = _log(agent, nation, password=password)
        except HTTPError as error:
            if error.code == 403:
                logger.error("%s's password is incorrect. Please try again.", nation)
            elif error.code == 404:
                logger.error("%s does not exist. Please revive it or check your spelling.", nation)
            elif error.code == 409:
                logger.info(
                    "%s was logged into too recently. Please wait a few moments before trying again.",
                    nation,
                )
            elif error.code == 429:
                print("The rate limit was exceeded and you've been locked out.")
                break
            elif error.code in range(500, 600):
                print("An internal server error occurred.")
                break
            else:
                logger.error(error)
                print("An unknown error occurred.")
                break
        except Exception as error:
            logger.exception(error)
            print(
                "Something went wrong with the script. Please contact Darcania with the above traceback at your earliest convenience."
            )
            break
        else:
            if data:
                to_add.update(data)
        finally:
            del password

    if not to_add:
        input("No data to save. Press enter to return to the menu . . . ")
        return

    print("Saving new nation tokens . . . ")
    tmp_name = ".tokens-%d.tmp" % random.randrange(1000, 10000)
    with open(tmp_name, "w", encoding="utf-8") as tokens_tmp:
        try:
            with open(".tokens", "r", encoding="utf-8") as tokens:
                for line in tokens:
                    nation, _ = tuple(map(str.strip, line.split(":")))
                    if nation in to_add:
                        line = "%s:%s\n" % (nation, to_add.pop(nation))
                    tokens_tmp.write(line)
        except FileNotFoundError:
            pass
        for tup in to_add.items():
            tokens_tmp.write("%s:%s\n" % tup)
    os.replace(tmp_name, ".tokens")

    input("Tokens updated. Press enter to return to the menu . . . ")


def remove_nations():
    try:
        if os.path.getsize(".tokens") == 0:
            raise FileNotFoundError()
    except FileNotFoundError:
        input("No nations are saved. Press enter to return to the menu . . . ")
        return
    to_remove = set()
    while True:
        nation = input("Nation: ")
        if not nation:
            break
        nation = "_".join(nation.strip().lower().split())
        if any(c not in "-0123456789_abcdefghijklmnopqrstuvwxyz" for c in nation):
            print("Invalid nation name.")
            continue
        to_remove.add(nation)

    if not to_remove:
        input("No nations to remove. Press enter to return to the menu . . . ")
        return

    print("Updating nation tokens . . . ")
    with open(".tokens.tmp", "w", encoding="utf-8") as tokens_tmp:
        try:
            with open(".tokens", "r", encoding="utf-8") as tokens:
                for line in tokens:
                    nation, _ = tuple(map(str.strip, line.split(":")))
                    if nation in to_remove:
                        continue
                    tokens_tmp.write(line)
        except FileNotFoundError:
            input("No nations are saved. Press enter to return to the menu . . . ")
            return
    os.replace(".tokens.tmp", ".tokens")

    input("Tokens updated. Press enter to return to the menu . . . ")


def list_nations():
    _, lines = os.get_terminal_size(2)
    try:
        with open(".tokens", "r", encoding="utf-8") as tokens:
            for i, line in enumerate(tokens):
                if i > 0 and i % (lines - 1) == 0:
                    input("  -- MORE --  ")
                nation, _ = tuple(map(str.strip, line.split(":")))
                print(" ".join(nation.split("_")).title())
    except FileNotFoundError:
        print("No nations have been saved.")
    print()
    input("No more nations. Press enter to return to the menu . . . ")


@static_vars(pause_next=None)
def _log(agent, nation, **kwargs):
    headers = {"User-Agent": agent}
    if "pin" in kwargs:
        headers["X-Pin"] = kwargs.pop("pin")
    elif "autologin" in kwargs:
        headers["X-Autologin"] = kwargs.pop("autologin")
    else:
        headers["X-Password"] = kwargs.pop("password")
    if kwargs:
        raise TypeError("Unexpected **kwargs: %r" % kwargs)

    if _log.pause_next:
        sleep_for = 30 - (time.time() - _log.pause_next)
        _log.pause_next = None
        if sleep_for > 0:
            logger.info("Sleeping for %s seconds to avoid rate limit.", sleep_for)
            time.sleep(sleep_for)
    try:
        with urlopen(
            Request(
                "https://www.nationstates.net/cgi-bin/api.cgi?nation=%s&q=notices" % nation,
                headers=headers,
            )
        ) as response:
            headers = response.headers
            root = ElementTree.fromstring(response.read())
    finally:
        if int(headers.get("X-ratelimit-requests-seen", 0)) >= min(
            max(1, 50 - rate_limit_buffer), 50
        ):
            _log.pause_next = time.time()

    for notices in root.findall("NOTICES"):
        for notice in notices.findall("NOTICE"):
            nnew = notice.find("NEW")
            ntype = notice.find("TYPE")
            if nnew is None or ntype.text in ("I", "U"):
                notices.remove(notice)
            else:
                notice.remove(nnew)
        if len(notices) == 0:
            root.remove(notices)

    print("\n%s\n" % minidom.parseString(ElementTree.tostring(root)).toprettyxml("    ", ""))
    return {root.attrib["id"]: headers["X-Autologin"]} if "X-Autologin" in headers else None


# tuple of two-tuples because order is important
main_menu_options = (
    (run, "Run the autologin script."),
    (set_agent, "Sets the script's user agent."),
    (add_nations, "Add or edit nations and passwords."),
    (remove_nations, "Remove nations from the list."),
    (list_nations, "List nation names without logging in to any of them."),
)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Uncaught exception: %s", exc_value, exc_info=(exc_type, exc_value, exc_traceback)
    )
    print(
        "Something went very wrong with the script. Please contact Darcania with the above error at your earliest convenience."
    )


if __name__ == "__main__":
    sys.excepthook = handle_exception
    main()
