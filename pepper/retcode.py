"""
A retcode validator

"""


class PepperRetcode:
    """
    Validation container
    """

    def validate(self, options, result):
        """
        Validate result dictionary retcode values.

        Without a --fail-* option the exit code follows the salt and salt-run
        commands: the retcode of a runner or wheel job that failed, otherwise 1
        if any minion returned a non-zero retcode, otherwise 0.

        :param options: optparse options

        :param result: list of returns from salt-api

        :return: exit code
        """
        if options.fail_any:
            return self.validate_fail_any(result)
        if options.fail_any_none:
            return self.validate_fail_any_none(result)
        if options.fail_all:
            return self.validate_fail_all(result)
        if options.fail_all_none:
            return self.validate_fail_all_none(result)
        return self.validate_salt(result)

    @staticmethod
    def _job_retcode(data):
        """
        The retcode of a runner or wheel job, found the way salt-run finds it

        :param data: the job data from a full_return runner or wheel return
        """
        if isinstance(data, dict) and "return" in data and "retcode" not in data:
            data = data["return"]
        if isinstance(data, dict) and "retcode" in data:
            return data["retcode"]
        if (
            isinstance(data, dict)
            and isinstance(data.get("data"), dict)
            and "retcode" in data["data"]
        ):
            return data["data"]["retcode"]
        return None

    @staticmethod
    def _minion_retcode(ret):
        retcode = ret["retcode"]
        # Salt can report a retcode for each state run, take the worst
        if isinstance(retcode, dict):
            return max(retcode.values(), default=0)
        return retcode

    @classmethod
    def retcodes(cls, result):
        """
        Collect retcodes from every return in result

        :param result: list of returns from salt-api

        :return: a tuple of the runner and wheel job retcodes and the minion
            retcodes
        """
        jobs = []
        minions = []
        if not isinstance(result, list):
            return jobs, minions
        for ret in result:
            if not isinstance(ret, dict):
                continue
            if "tag" in ret and isinstance(ret.get("data"), dict):
                retcode = cls._job_retcode(ret["data"])
                if retcode is not None:
                    jobs.append(retcode)
                continue
            for minion_ret in ret.values():
                if (
                    isinstance(minion_ret, dict)
                    and minion_ret.get("retcode") is not None
                ):
                    minions.append(cls._minion_retcode(minion_ret))
        return jobs, minions

    @classmethod
    def _all_retcodes(cls, result):
        jobs, minions = cls.retcodes(result)
        return jobs + minions

    @classmethod
    def validate_salt(cls, result):
        """
        Return the exit code the salt or salt-run command would use

        :param result: list of returns from salt-api

        :return: exit code
        """
        jobs, minions = cls.retcodes(result)
        failed_job = next((r for r in jobs if r != 0), None)
        if failed_job is not None:
            return failed_job
        if any(r != 0 for r in minions):
            return 1
        return 0

    @classmethod
    def minions_failed(cls, result):
        """
        Whether any minion returned a non-zero retcode
        """
        return any(r != 0 for r in cls.retcodes(result)[1])

    @classmethod
    def validate_fail_any(cls, result):
        """
        Validate result dictionary retcode values.
        Returns 0 if no retcode keys.
        Returns first non zero retcode if any of recodes is non zero.

        :param result: list of returns from salt-api

        :return: exit code
        """
        retcodes = cls._all_retcodes(result)
        return next((r for r in retcodes if r != 0), 0)

    @classmethod
    def validate_fail_any_none(cls, result):
        """
        Validate result dictionary retcode values.
        Returns -1 if no retcode keys.
        Returns first non zero retcode if any of recodes is non zero.

        :param result: list of returns from salt-api

        :return: exit code
        """
        retcodes = cls._all_retcodes(result)
        if not retcodes:
            return -1  # there are no retcodes
        return next((r for r in retcodes if r != 0), 0)

    @classmethod
    def validate_fail_all(cls, result):
        """
        Validate result dictionary retcode values.
        Returns 0 if no retcode keys.
        Returns first non zero retcode if all recodes are non zero.

        :param result: list of returns from salt-api

        :return: exit code
        """
        retcodes = cls._all_retcodes(result)
        if retcodes and all(r != 0 for r in retcodes):
            return retcodes[0]
        return 0

    @classmethod
    def validate_fail_all_none(cls, result):
        """
        Validate result dictionary retcode values.
        Returns -1 if no retcode keys.
        Returns first non zero retcode if all recodes are non zero.

        :param result: list of returns from salt-api

        :return: exit code
        """
        retcodes = cls._all_retcodes(result)
        if not retcodes:
            return -1  # there are no retcodes
        if all(r != 0 for r in retcodes):
            return retcodes[0]
        return 0
