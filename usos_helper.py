import argparse
import sys
import scripts.planner.planner
import scripts.deleter
import scripts.downloader
import scripts.course_search
import scripts.cart_course_codes_getter

def add_credentials_option (parser) -> None:
    parser.add_argument('-l', '--login', metavar='FILE', help='Usos login data file')
    parser.add_argument('-a', '--anon', action='store_true', help='Anonymous session')


def add_pattern_option (parser):
    parser.add_argument('-p', '--pattern', metavar='PATTERN', help='Regex pattern to match')

def add_cycle_option (parser) -> None:
    parser.add_argument('-c', '--cycle', metavar='CYCLE', help='Dydactic cycle')

def add_deleter_options (deleter_parser):
    add_credentials_option (deleter_parser)
    add_pattern_option (deleter_parser)

def add_downloader_options (downloader_parser) -> None:
    add_cycle_option (downloader_parser)

def add_search_options (_) -> None:
    pass

def add_planner_options (planner_parser) -> None:
    add_credentials_option (planner_parser)

def add_cart_options (cart_parser) -> None:
    add_credentials_option (cart_parser)

def main () -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='usos tools program', dest='command')

    deleter_parser = subparsers.add_parser("delete")
    add_deleter_options (deleter_parser)
    downloader_parser = subparsers.add_parser("download")
    add_downloader_options (downloader_parser)
    search_parser = subparsers.add_parser("search")
    add_search_options (search_parser)
    planner_parser = subparsers.add_parser("plan")
    add_planner_options (planner_parser)
    cart_parser = subparsers.add_parser("cart")
    add_cart_options (cart_parser)

    args = parser.parse_args()

    match args.command:
        case 'delete':
            scripts.deleter.main(args)
        case 'download':
            scripts.downloader.main(args)
        case 'search':
            scripts.course_search.main(args)
        case 'plan':
            scripts.planner.planner.main(args)
        case 'cart':
            scripts.cart_course_codes_getter.main(args)

    return 0

if __name__ == '__main__':
    sys.exit(main())
