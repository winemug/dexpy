#!/usr/bin/python
import argparse

def main():
    parser = argparse.ArgumentParser()

    # parser.add_argument("location", choices=[ "eu", "us" ])
    # parser.add_argument("-u", "--username", required = True)
    # parser.add_argument("-p", "--password", required = True)
    # parser.add_argument("-i", "--sessionid", required = False)
    parser.add_argument("-v", "--verbose", required = False, default = False, action='store_true')

    args = parser.parse_args()

    try:
        raw_input()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()