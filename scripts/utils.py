from getpass import getpass

def get_login_credentials (args) -> tuple[str, str] | None:
    if args.anon:
        return None
    if args.login:
        login_filename = args.login
        with open (login_filename, 'r', encoding="utf-8") as login_file:
            credentials = login_file.read().split('\n')
            if len(credentials) < 2:
                raise RuntimeError('Failed to read credentials')
            username = credentials[0]
            password = credentials[1]
    else:
        username = input('username:')
        password = getpass()
    return username, password

def get_pattern (args) -> str:
    if args.pattern:
        return args.pattern
    print ('Enter regular expression to match:')
    return input ()

def get_cycle (args) -> str:
    if args.cycle:
        return args.cycle
    return input('cycle:')
def read_words_from_file (filename: str) -> list[str]:
    """Returns a list of all words in the file."""
    try:
        with open (filename, 'r', encoding="utf-8") as f:
            return f.read().split()
    except FileNotFoundError:
        return []
