"""The kits' command-line convention: JSON on stdout for successes and failures, exit 0 or 1."""
import argparse

from .errors import KitError
from .jsonio import output


class ArgumentParser(argparse.ArgumentParser):
    """Argument errors become KitError('/arguments'), reported as JSON like any other error."""
    error_class = KitError

    def error(self, message):
        raise self.error_class('/arguments', message)


def parser_class(error):
    return type('ArgumentParser',(ArgumentParser,),{'error_class':error})


def fail(error):
    """Prints the failure object for an exception (its report, if any, plus the error)."""
    output({**getattr(error,'report',{}),'ok':False,'errors':[{'path':getattr(error,'path','/input'),'message':str(error)}]})
    return 1
