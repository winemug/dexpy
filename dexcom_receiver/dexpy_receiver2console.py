#!/usr/bin/python
import argparse
from dexpy_receiver import ReceiverSession
import readdata

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", required = False, default = False, action='store_true')

    args = parser.parse_args()

    session = ReceiverSession()
    session.startMonitoring()
    
    try:
        raw_input()
    except KeyboardInterrupt:
        pass

    session.stopMonitoring()

if __name__ == '__main__':
    main()
