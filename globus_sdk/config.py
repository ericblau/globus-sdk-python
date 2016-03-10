"""
Load config files once per interpreter invocation.
"""

import os
from ConfigParser import SafeConfigParser, NoOptionError

# use StringIO to wrap up reads from file-like objects in new file-like objects
# import it in a py2/py3 safe way
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


def _get_lib_config_path():
    """
    Get the location of the default config file in globus_sdk
    This could be made part of GlobusConfigParser, but it really doesn't handle
    any class-specific state. Just a helper for getting the location of a file.
    """
    fname = "globus.cfg"
    try:
        import pkg_resources
        path = pkg_resources.resource_filename("globus_sdk", fname)
    except ImportError:
        pkg_path = os.path.dirname(__file__)
        path = os.path.join(pkg_path, fname)
    return path


class GlobusConfigParser(object):
    """
    Wraps a SafeConfigParser to do modified get()s and config file loading.
    """
    _GENERAL_CONF_SECTION = 'general'

    def __init__(self):
        self._parser = SafeConfigParser()
        self._load_config()

    def _load_config(self):
        # TODO: /etc is not windows friendly, not sure about expanduser
        self._read([_get_lib_config_path(), "/etc/globus.cfg",
                    os.path.expanduser("~/.globus.cfg")])

    def _read(self, filenames):
        """
        Wraps up self._parser.read() to inject '[general]\n' at the beginning
        of file contents.
        Originally, this was implemented by catching
        MissingSectionHeaderErrors, but that's actually overcomplicated and
        unnecessary. Always inserting it, uniformly, is simpler and doesn't
        change the semantics of config parsing at all.
        """
        for fname in filenames:
            try:
                with open(fname) as f:
                    # wrap the file-like object in a StringIO so that we can
                    # pass it to the SafeConfigParser as a file like object
                    wrapped_file = StringIO(
                        '[{}]\n'.format(self._GENERAL_CONF_SECTION) + f.read())
                    self._parser.readfp(wrapped_file, fname)
            except IOError:
                continue

    def get(self, option,
            section=None, environment=None,
            failover_to_general=False, check_env=False):
        """
        Attempt to lookup an option in the config file. Optionally failover to
        the general section if the option is not found.

        Also optionally, check for a relevant environment variable, which is
        named always as GLOBUS_SDK_{option.upper()}. Note that 'section'
        doesn't slot into the naming at all. Otherwise, we'd have to contend
        with GLOBUS_SDK_GENERAL_... for almost everything, and
        GLOBUS_SDK_ENVIRONMENT\ PROD_... which is awful.

        Returns None for an unfound key, rather than raising a NoOptionError.
        """
        # envrionment is just a fancy name for sections that start with
        # 'environment '
        if environment:
            section = 'environment ' + environment
        # if you don't specify a section or an environment, assume it's the
        # general conf section
        if section is None:
            section = self._GENERAL_CONF_SECTION

        # if this is a config option which checks the environment, look there
        # *first* for a value -- env values have higher precedence than config
        # files so that you can locally override the behavior of a command in a
        # given shell or subshell
        env_option_name = 'GLOBUS_SDK_{}'.format(option.upper())
        if check_env and env_option_name in os.environ:
            return os.environ[env_option_name]

        try:
            return self._parser.get(section, option)
        except NoOptionError:
            if failover_to_general:
                return self.get(option, section=self._GENERAL_CONF_SECTION)
            return None


def _get_parser():
    """
    Singleton pattern implemented via a global varaible and function.
    There is only ever one _parser, and it is always returned by this function.
    """
    global _parser
    if _parser is None:
        _parser = GlobusConfigParser()
    return _parser
# at import-time, it's None
_parser = None


def get_service_url(environment, service):
    p = _get_parser()
    option = service + "_service"
    # TODO: validate with urlparse?
    return p.get(option, environment=environment)


def get_auth_token(environment):
    """
    Fetch any auth token from the config, if one is present
    """
    p = _get_parser()

    tkn = p.get('auth_token', environment=environment,
                failover_to_general=True, check_env=True)

    return tkn
