#!/usr/bin/env python
"""
A CLI interface to a remote salt-api instance
"""
import json
import logging
import sys

from pepper.cli import PepperCli
from pepper.exceptions import (
    PepperArgumentsException,
    PepperAuthException,
    PepperException,
)
from pepper.retcode import PepperRetcode

try:
    import salt.config
    import salt.loader
    import salt.output

    HAS_SALT = True
except ImportError:
    HAS_SALT = False

logger = logging.getLogger(__name__)

NO_MINIONS_MATCHED = (
    "No minions matched the target. No command was sent, no jid was assigned."
)


class Pepper:
    def __init__(self):
        self.cli = PepperCli()
        if HAS_SALT:
            self.opts = salt.config.client_config(self.cli.options.master)
        else:
            self.opts = {}
        if self.cli.options.output_file is not None:
            self.opts["output_file"] = self.cli.options.output_file
        if self.cli.options.state_output is not None:
            self.opts["state_output"] = self.cli.options.state_output
        if self.cli.options.state_verbose is not None:
            # Parsed the same way as salt's --state-verbose
            self.opts["state_verbose"] = {
                "true": True,
                "false": False,
            }.get(
                self.cli.options.state_verbose.lower(), self.cli.options.state_verbose
            )

    @property
    def output(self):
        if not hasattr(self, "modules"):
            self.modules = salt.loader.minion_mods(self.opts)
        try:
            oput = self.modules[self.cli.args[1]].__outputter__
        except (KeyError, AttributeError, TypeError):
            oput = "nested"
        return oput

    def validate(self, data):
        """
        Return the exit code for the results, warning like salt does when a
        minion failed
        """
        options = self.cli.options
        retcode = PepperRetcode().validate(options, data)
        fail_options = (
            options.fail_any,
            options.fail_any_none,
            options.fail_all,
            options.fail_all_none,
        )
        if (
            not any(fail_options)
            and options.client.startswith("local")
            and PepperRetcode.no_minions_matched(data)
        ):
            # The salt command prints this and exits with 2
            print(NO_MINIONS_MATCHED, file=sys.stderr)
            return 2
        if retcode and not any(fail_options) and PepperRetcode.minions_failed(data):
            print("ERROR: Minions returned with non-zero exit code", file=sys.stderr)
        return retcode

    def write(self, result):
        """
        Print raw JSON output to stdout or the output file
        """
        if self.cli.options.output_file is not None:
            with open(self.cli.options.output_file, "a", encoding="utf-8") as ofile:
                print(result, file=ofile)
        else:
            print(result)

    def write_polled(self, polled):
        """
        Print the returns the --fail-if-incomplete poller collected as one JSON
        document
        """
        if polled:
            self.write(json.dumps({"return": polled}, sort_keys=True, indent=4))
            polled.clear()

    def __call__(self):
        polled = []
        try:
            retcode = None
            for exit_code, result in self.cli.run():
                data = json.loads(result)
                # unwrap ret in some cases
                if "return" in data:
                    data = data["return"]

                if HAS_SALT and self.opts:
                    logger.debug("Use Salt outputters")
                    for ret in data:
                        if isinstance(ret, dict):
                            if self.cli.options.client.startswith("local"):
                                for minionid, minionret in ret.items():
                                    # rest_tornado doesnt return full_return directly
                                    # it will always be from get_event, so the output differs slightly
                                    if (
                                        isinstance(minionret, dict)
                                        and "return" in minionret
                                    ):
                                        # version >= 2017.7
                                        salt.output.display_output(
                                            {minionid: minionret["return"]},
                                            self.cli.options.output
                                            or minionret.get("out", None)
                                            or "nested",
                                            opts=self.opts,
                                        )
                                    # cherrypy returns with ret via full_return
                                    elif (
                                        isinstance(minionret, dict)
                                        and "ret" in minionret
                                    ):
                                        # version >= 2017.7
                                        salt.output.display_output(
                                            {minionid: minionret["ret"]},
                                            self.cli.options.output
                                            or minionret.get("out", None)
                                            or "nested",
                                            opts=self.opts,
                                        )
                                    else:
                                        salt.output.display_output(
                                            {minionid: minionret},
                                            self.cli.options.output or self.output,
                                            opts=self.opts,
                                        )
                            elif "data" in ret:
                                # unfold runners
                                outputter = ret.get("outputter", "nested")
                                if (
                                    isinstance(ret["data"], dict)
                                    and "return" in ret["data"]
                                ):
                                    ret = ret["data"]["return"]
                                salt.output.display_output(
                                    ret,
                                    self.cli.options.output or outputter,
                                    opts=self.opts,
                                )
                            else:
                                salt.output.display_output(
                                    {self.cli.options.client: ret},
                                    self.cli.options.output
                                    or ret.get("outputter", "nested"),
                                    opts=self.opts,
                                )
                        else:
                            salt.output.display_output(
                                {self.cli.options.client: ret},
                                self.cli.options.output or "nested",
                                opts=self.opts,
                            )
                elif self.cli.options.fail_if_minions_dont_respond:
                    # The poller yields each minion as it returns. Without
                    # salt's outputters, print them as one JSON document.
                    polled.extend(data)
                else:
                    self.write(result)
                if exit_code is not None:
                    if self.cli.options.fail_if_minions_dont_respond:
                        # jobs.lookup_jid returns no retcodes, so the poller's
                        # exit code only says whether every minion returned
                        retcode = exit_code
                        if PepperRetcode.no_minions_matched(data):
                            print(NO_MINIONS_MATCHED, file=sys.stderr)
                    elif exit_code == 0:
                        retcode = self.validate(data)
                    else:
                        retcode = exit_code
                    break
            self.write_polled(polled)
            return retcode
        except (PepperException, PepperAuthException, PepperArgumentsException) as exc:
            # Keep the returns the poller collected before the error
            self.write_polled(polled)
            print(f"Pepper error: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            self.write_polled(polled)
            # TODO: mimic CLI and output JID on ctrl-c
            return 0
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.write_polled(polled)
            print(
                f"Uncaught Pepper error: {e} (increase verbosity for the full traceback).",
                file=sys.stderr,
            )
            logger.debug("Uncaught traceback:", exc_info=True)
            return 1


def main():
    """
    Entry point for the pepper command
    """
    exit_code = Pepper()()
    raise SystemExit(exit_code if exit_code is not None else 0)
