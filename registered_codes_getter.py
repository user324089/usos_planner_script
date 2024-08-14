"""Program that downloads the courses that a user is registered to"""
import argparse
from getpass import getpass
import usos_tools.login
import sys
import usos_tools.cart

def get_login_credentials() -> tuple[str, str]:
    """Gets login credentials from a file or from the user."""
    parser = argparse.ArgumentParser(description='Usos planner')
    parser.add_argument('-l', '--login', metavar='FILE', help='Usos login data file')
    args = parser.parse_args()
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

def main ():
    map_cycle_to_codes = usos_tools.cart.get_cart_subject_codes ( usos_tools.login.log_in_to_usos(*get_login_credentials()))
    for cycle, codes in map_cycle_to_codes.items():
        print (cycle)
        for code in codes:
            print ('\t' + code)

if __name__ == '__main__':
    sys.exit(main())
