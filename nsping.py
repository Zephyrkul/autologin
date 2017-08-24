import os
import logging
from getpass import getpass
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from xml.etree import ElementTree
from xml.dom import minidom

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


rate_limit_buffer = 10


filename = os.path.splitext(os.path.basename(__file__))[0] + ".json"
defaultagent = "{} (Darcania's autologin script)"


class Delete(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


def static_vars(**kwargs):
    def decorate(func):
        for k, v in kwargs.items():
            setattr(func, k, v)
        return func
    return decorate


def main():
    nations = {}
    if os.path.isfile(filename):
        with open(filename, mode="r") as nationfile:
            nations = json.load(nationfile)
    nations_copy = nations.copy()

    if "AGENT" not in nations:
        agent = input("User Agent: ")
        while not agent:
            agent = input("You must supply a User Agent: ")
        nations["AGENT"] = defaultagent.format(agent)
        print("User agent set!")
    for nation, autologin in nations_copy.items():
        if nation == "AGENT":
            continue
        try:
            _log(nations["AGENT"], nation, autologin=autologin)
        except Delete as error:
            # 403 Forbidden (wrong password) or 404 Not Found (nonexistent nation)
            del nations[nation]
            logger.exception(error.__cause__)
        except HTTPError as error:
            logger.exception(error)
        except Exception as error:
            logger.exception(error)
            break
    else:
        while True:
            nation = input("Nation: ")
            if not nation:
                break
            if nation == "RESET":
                if input("Warning: This will reset your user agent and saved nations! Continue? [y/N] ").strip().lower() in ("yes", "y"):
                    nations_copy = {}
                    input("Data reset. Press enter to continue... ")
                    break
                else:
                    print("Okay, I won't reset your nations.")
                    continue
            nation = nation.strip().lower().replace(" ", "_")
            if any(c not in "-0123456789_abcdefghijklmnopqrstuvwxyz" for c in nation):
                print("Invalid nation name.")
                continue
            if nation in nations:
                if input("That nation is already logged. Would you like to remove it? [y/N] ").strip().lower() in ("yes", "y"):
                    del nations[nation]
                    print("Nation removed.")
                else:
                    print("Okay, I won't remove that nation.")
                continue
            password = getpass()
            if password:
                try:
                    data = _log(nations["AGENT"], nation, password=password)
                except Delete as error:
                    del nations[nation]
                    logger.exception(error.__cause__)
                except HTTPError as error:
                    logger.exception(error)
                except Exception as error:
                    logger.exception(error)
                    break
                else:
                    if data:
                        nations.update(data)
                finally:
                    del password

    if nations != nations_copy:
        with open(filename, mode="w") as nationfile:
            json.dump(nations, nationfile)


@static_vars(pause_next=None)
def _log(agent: str, nation: str, **kwargs: str):
    headers = {"User-Agent": agent}
    if "pin" in kwargs:
        headers["X-Pin"] = kwargs.pop("pin")
    elif "autologin" in kwargs:
        headers["X-Autologin"] = kwargs.pop("autologin")
    else:
        headers["X-Password"] = kwargs.pop("password")
    if kwargs:
        raise TypeError("Unexpected **kwargs", str(kwargs))

    if _log.pause_next:
        sleep_for = 30 - (time.time() - _log.pause_next)
        _log.pause_next = None
        if sleep_for > 0:
            logger.info("Sleeping for %s seconds to avoid rate limit.", sleep_for)
            time.sleep(sleep_for)
    try:
        with urlopen(Request("https://www.nationstates.net/cgi-bin/api.cgi?nation={}&q=notices".format(nation), headers=headers)) as response:
            headers = response.headers
            root = ElementTree.fromstring(response.read())
    except HTTPError as error:
        headers = error.headers
        if error.status == 429:
            raise RateLimitExceeded(headers.pop("X-Retry-After", "0")) from error
        if error.status in (403, 404):
            raise Delete() from error
        raise
    finally:
        if int(headers["X-ratelimit-requests-seen"]) >= min(max(1, 50 - rate_limit_buffer), 50):
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

    logger.info("\n%s\n", minidom.parseString(ElementTree.tostring(root)).toprettyxml("    ", ""))
    return {root.attrib["id"]: headers["X-Autologin"]} if "X-Autologin" in headers else None


if __name__ == "__main__":
    main()
