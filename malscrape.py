#!/usr/bin/env python3.7
import asyncio
from argparse import ArgumentParser
from getpass import getpass
from importlib import reload

import mal_user_scraper

async def main():
    parser = ArgumentParser()
    parser.add_argument("-n", "--name", dest="name", type=str, default='',
                        help="found users names must match this")
    parser.add_argument("-o", "--older", dest="older", type=int, default=0,
                        help="found users must be older than this (in years)")
    parser.add_argument("-y", "--younger", dest="younger", type=int, default=0,
                        help="found users must be younger than this (in years)")
    parser.add_argument("-l", "--location", dest="location", type=str, default='',
                        help="found users must live here")
    parser.add_argument("-g", "--gender", dest="gender", type=str, default=0,
                        help="found users must be of this gender_id (0=irrelevant, 1=male, 2=female, 3=non-binary}")
    parser.add_argument("-f", "--from", dest="from_page", type=int, default=1,
                        help="lower boundary of the search pages to scrape (boundaries are included)")
    parser.add_argument("-t", "--to", dest="to_page", type=int, default=1,
                        help="upper boundary of the search pages to scrape (boundaries are included)")
    parser.add_argument("-db", "--database", dest="db", default='users.db',
                        help="file path of the sqlite3 database")
    args = parser.parse_args()
    username = input('Your myanimelist.net username: ')
    password = getpass('Your myanimelist.net password: ')
    for page_count in range(args.from_page, args.to_page + 1):
        await mal_user_scraper.run(
            page=page_count, username=username, password=password,
            name=args.name, older=args.older, younger=args.younger,
            location=args.location, gender=args.gender, db_path=args.db
        )
        reload(mal_user_scraper)

if __name__ == '__main__':
    asyncio.run(main())
