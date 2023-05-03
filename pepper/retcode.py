'''
A retcode validator

'''


class PepperRetcode(object):
    '''
    Validation container
    '''

    def validate(self, options, result):
        '''
        Validate result dictionary retcode values.

        :param options: optparse options

        :param result: dictionary from Saltstack master

        :return: exit code
        '''
        if options.fail_any:
            return self.validate_fail_any(result)
        if options.fail_any_none:
            return self.validate_fail_any_none(result)
        if options.fail_all:
            return self.validate_fail_all(result)
        if options.fail_all_none:
            return self.validate_fail_all_none(result)
        return 0

    @staticmethod
    def gen_dict_extract(var, key):
        '''
        Generator function that yields all values for key in dictionary

        :param var: dictionary or list of dictionaries

        :param key: key name

        :return: generator object containing values of key
        '''
        if isinstance(var, dict):
            for k, v in var.items():
                if k == key:
                    yield v
                if isinstance(v, (dict, list)):
                    for result in PepperRetcode.gen_dict_extract(v, key):
                        yield result
        elif isinstance(var, list):
            for d in var:
                for result in PepperRetcode.gen_dict_extract(d, key):
                    yield result

    @staticmethod
    def validate_fail_any(result):
        '''
        Validate result dictionary retcode values.
        Returns 0 if no retcode keys.
        Returns first non zero retcode if any of recodes is non zero.

        :param result: dictionary from Saltstack master

        :return: exit code
        '''
        retcodes = list(PepperRetcode.gen_dict_extract(result, 'retcode'))
        return next((r for r in retcodes if r != 0), 0)

    @staticmethod
    def validate_fail_any_none(result):
        '''
        Validate result dictionary retcode values.
        Returns -1 if no retcode keys.
        Returns first non zero retcode if any of recodes is non zero.

        :param result: dictionary from Saltstack master

        :return: exit code
        '''
        retcodes = list(PepperRetcode.gen_dict_extract(result, 'retcode'))
        if not retcodes:
            return -1  # there are no retcodes
        return next((r for r in retcodes if r != 0), 0)

    @staticmethod
    def validate_fail_all(result):
        '''
        Validate result dictionary retcode values.
        Returns 0 if no retcode keys.
        Returns first non zero retcode if all recodes are non zero.

        :param result: dictionary from Saltstack master

        :return: exit code
        '''
        retcodes = list(PepperRetcode.gen_dict_extract(result, 'retcode'))
        if all(r != 0 for r in retcodes):
            return next((r for r in retcodes if r != 0), 0)
        return 0

    @staticmethod
    def validate_fail_all_none(result):
        '''
        Validate result dictionary retcode values.
        Returns -1 if no retcode keys.
        Returns first non zero retcode if all recodes are non zero.

        :param result: dictionary from Saltstack master

        :return: exit code
        '''
        retcodes = list(PepperRetcode.gen_dict_extract(result, 'retcode'))
        if not retcodes:
            return -1  # there are no retcodes
        if all(r != 0 for r in retcodes):
            return next((r for r in retcodes if r != 0), 0)
        return 0
