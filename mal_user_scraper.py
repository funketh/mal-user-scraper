# The MIT License (MIT)
# Copyright (c) 2019 Theodor Funke
# Copyright (c) 2016 Vladimir Ignatev
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
# OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# NOTE: This script only scrapes Anime related data
import asyncio
import logging
import re
import sqlite3
import sys
from argparse import ArgumentParser
from collections import namedtuple
from datetime import datetime, timedelta
from getpass import getpass
from typing import Optional

import aiohttp

async def main():
    logging.basicConfig(filename='info.log', level=logging.INFO)
    args = parse_cmd_args()
    async with aiohttp.ClientSession() as session:
        await login(session)
        search_jobs = [users_from_search_page(session, p, args.name, args.location,
                                              args.older, args.younger, args.gender) for p in range(args.pages)]
        user_urls = ['https://myanimelist.net' + url
                     for sublist in await asyncio.gather(*search_jobs) for url in sublist]
        user_jobs = [page_text(session, url) for url in user_urls]
        user_pages = await asyncio.gather(*user_jobs)
    total = len(user_urls)
    users = []
    for i, page in enumerate(user_pages):
        try:
            users.append(get_user_data(page))
        except Exception:
            logging.exception('Ignoring exception: ')
        progress(i, total)
    try:
        check_if_no_affinities(users)
    except WantsToExit:
        return
    save_to_db(args.db, users)


# Interface
def parse_cmd_args():
    parser = ArgumentParser()
    parser.add_argument("-n", "--name", dest="name", type=str, default='',
                        help="found users names must match this")
    parser.add_argument("-o", "--older", dest="older", type=int, default=0,
                        help="found users must be older than this (in years)")
    parser.add_argument("-y", "--younger", dest="younger", type=int, default=0,
                        help="found users must be younger than this (in years)")
    parser.add_argument("-l", "--location", dest="location", type=str, default='',
                        help="found users must live here")
    parser.add_argument("-g", "--gender", dest="gender", type=str, default='irrelevant',
                        help="found users must be of this gender_id (0=irrelevant, 1=male, 2=female, 3=non-binary}")
    parser.add_argument("-p", "--pages", dest="pages", type=int, default=1,
                        help="how many pages of users to scrape (1 page = 24 users)")
    parser.add_argument("-d", "--delay", dest="delay", type=float, default=0.3,
                        help="delay in seconds between the user page requests")
    parser.add_argument("-db", "--database",
                        action="store_false", dest="db", default='users.db',
                        help="file path of the sqlite3 database")
    return parser.parse_args()

def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))
    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)
    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()


# Web requests
async def login(session):
    await session.post('https://myanimelist.net/login.php', data={
        'action': 'login',
        'username': input('Your myanimelist.net username: '),
        'password': getpass('Your myanimelist.net password: '),
    })

async def users_from_search_page(session, page_num, name, location, older, younger, gender):
    params = {
        'q': name,
        'loc': location,
        'agelow': older,
        'agehigh': younger,
        'g': gender,
        'show': str(page_num * 24),
    }
    async with session.get('https://myanimelist.net/users.php', params=params) as resp:
        return re.findall(r'(?<=<div class="picSurround"><a href=").+?(?=">)',
                          await resp.text())

async def page_text(session, url):
    async with session.get(url) as resp:
        return await resp.text()


User = namedtuple('User', ['name', 'last_online', 'gender', 'birthday', 'joined',
                           'location', 'shared', 'affinity', 'friend_count', 'days',
                           'mean_score', 'completed'])

# Scraping user data
def get_user_data(p) -> User:
    return User(
        name=safe_re_search(r"<span.*?>\s*(.*?)'s Profile", p),
        last_online=without_seconds(mal_to_datetime(safe_re_search(r"Last Online</span>.*?>(.*?)</span>", p))),
        gender=safe_re_search(r"Gender</span>.*?>(.*?)</span>", p),
        birthday=to_date(mal_to_datetime(safe_re_search(r"Birthday</span>.*?>(.*?)</span>", p))),
        location=safe_re_search(r"Location</span>.*?>(.*?)</span>", p),
        joined=to_date(
            mal_to_datetime(safe_re_search(r'Joined</span><span class="user-status-data di-ib fl-r">(.*?)<', p))),
        shared=safe_int(safe_re_search(r'class="fs11">(\d+?) Shared', p)),
        affinity=scrape_affinity(p),
        friend_count=safe_int(safe_re_search(r'All \(([\d,]+?)\)</a>Friends</h4>', p)),
        days=safe_float(safe_re_search(r'Anime Stats</h5>\s*<.*?>\s*<.*?><.*?>Days: </span>([\d,]+\.*\d*)</div>', p)),
        mean_score=safe_float(safe_re_search(r'Mean Score: </span>([\d,]+\.*\d*)', p)),
        completed=safe_int(safe_re_search(r'Completed</a><span class="di-ib fl-r lh10">([\d,]+)', p)),
    )

def scrape_affinity(page):
    match = re.search(r'<div class="bar-outer-negative ar"><.*?>[-]?([-]?\d+\.*\d*)%'
                      r'.*?</span></div>\s*<div class="bar-outer-positive al"><.*?>.*?(\d+\.*\d*)%', page)
    if match:
        return float(match.group(1)) or float(match.group(2))

def safe_re_search(*args, **kwargs) -> Optional[str]:
    match = re.search(*args, **kwargs)
    if match is None:
        return None
    return match.group(1)


# Helper functions
def mal_to_datetime(mal_time: str) -> Optional[datetime]:
    if not mal_time:
        return None
    # now or seconds
    if mal_time == 'Now' or 'second' in mal_time:
        return datetime.now()
    # minutes or hours
    m_or_h = re.match(r'(\d{1,2}) (minute|hour).*?', mal_time)
    if m_or_h:
        if m_or_h.group(2) == 'minute':
            return datetime.now() - timedelta(minutes=int(m_or_h.group(1)))
        return datetime.now() - timedelta(hours=int(m_or_h.group(1)))
    # today or yesterday
    t_or_y = re.match(r'(Today|Yesterday), (.+)', mal_time)
    if t_or_y:
        day = datetime.now().day - 1 if t_or_y.group(1) == 'Yesterday' else datetime.now().day
        time_ = datetime.strptime(t_or_y.group(2), '%I:%M %p')
        return datetime.now().replace(day=day, hour=time_.hour, minute=time_.minute)
    # several timestamp formats
    formats = (
        ('%b %d, %Y %I:%M %p', lambda d: d),  # full timestamp
        ('%b %d, %I:%M %p', lambda d: d.replace(year=datetime.now().year)),  # current year timestamp
        ('%b %d, %Y', lambda d: d),  # complete birthday
        ('%b %d', lambda d: d),  # birthday month and day
        ('%b', lambda d: d),  # birthday month
        ('%Y', lambda d: d),  # birthday year
    )
    for f, cleanup in formats:
        try:
            return cleanup(datetime.strptime(mal_time, f))
        except ValueError:
            pass

def without_seconds(date_time: Optional[datetime]) -> Optional[str]:
    if date_time:
        return date_time.replace(microsecond=0).isoformat(' ')[:-3]

def to_date(date_time: Optional[datetime]) -> Optional[str]:
    if date_time:
        return date_time.date().isoformat()

def safe_int(text: str) -> Optional[int]:
    if text is not None:
        return int(text.replace(',', ''))

def safe_float(text: str) -> Optional[float]:
    if text is not None:
        return float(text.replace(',', ''))


class WantsToExit(BaseException): pass

def check_if_no_affinities(users):
    if not any(u.affinity is not None for u in users):
        answer = input('No Affinities could be fetched. '
                       'This could mean that your login was unsuccessful. '
                       'Do you want to save the data anyway? (y/N): ')
        if answer.lower() not in ('y', 'yes'):
            raise WantsToExit


# Database
def save_to_db(db_path, users):
    db = sqlite3.connect(db_path)
    with db:
        db.execute('''CREATE TABLE IF NOT EXISTS user(
            name TEXT PRIMARY KEY,
            last_online TEXT,
            gender TEXT,
            birthday TEXT,
            joined TEXT,
            location TEXT,
            shared INTEGER,
            affinity REAL,
            friend_count INTEGER,
            days INTEGER,
            mean_score REAL,
            completed INTEGER
        )''')
        db.executemany('REPLACE INTO user' + str(User._fields)
                       + ' VALUES (' + ('?,' * len(User._fields))[:-1] + ')', users)

if __name__ == '__main__':
    asyncio.run(main())
