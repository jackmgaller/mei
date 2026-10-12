"""The kits' command-line convention: JSON on stdout for successes and failures, exit 0 or 1;
the commands that print plain text by default print JSON with --json, and every command takes
--json."""
import argparse
import sys

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


def add_json(sub, text_commands):
    """--json on every command of a subparsers action that does not have it yet. text_commands
    {name: what it prints without --json} have their own --json already; on the others --json
    is accepted and changes nothing, JSON being their output already."""
    for name,cmd in sub.choices.items():
        if '--json' in cmd._option_string_actions: continue
        cmd.add_argument('--json',action='store_true',
                         help=f'The result as JSON (default: {text_commands[name]}).' if name in text_commands else
                              'The result as JSON: the default for this command, accepted on every command.')


def wants_text(argv, args, text_commands):
    """Whether a command prints plain text (and so its failure too): one of text_commands without
    --json. args is None when the arguments did not parse; argv is then read as given."""
    if args is not None:
        return args.command in text_commands and not getattr(args,'json',False)
    given = sys.argv[1:] if argv is None else list(argv)
    return bool(given) and given[0] in text_commands and '--json' not in given
