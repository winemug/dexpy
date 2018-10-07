#!/usr/bin/python
import sharesession
import argparse

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("location", choices=[ "eu", "us" ])
    parser.add_argument("-u", "--username", required = True)
    parser.add_argument("-p", "--password", required = True)
    parser.add_argument("-i", "--sessionid", required = False)
    parser.add_argument("-v", "--verbose", required = False, default = False, action='store_true')

    args = parser.parse_args()

    session = sharesession.ShareSession(args.location, args.username, args.password, args.sessionid, args.verbose)
    session.startMonitoring()
    try:
        raw_input()
    except KeyboardInterrupt:
        pass
    session.stopMonitoring()

if __name__ == '__main__':
    main()
