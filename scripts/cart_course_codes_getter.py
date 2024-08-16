"""Module that downloads the courses that user is registered for"""
import usos_tools.login
import usos_tools.cart
from scripts.utils import get_login_credentials

def main (args):
    map_cycle_to_codes = usos_tools.cart.get_cart_subject_codes(
        usos_tools.login.log_in_to_usos(*get_login_credentials(args))
    )
    for cycle, codes in map_cycle_to_codes.items():
        print (cycle)
        for code in codes:
            print ('\t' + code)