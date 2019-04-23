# NOTE: This script only scrapes Anime related data
import re
import sqlite3
import time
import traceback
from argparse import ArgumentParser
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Optional, List

from selenium.webdriver import Firefox, FirefoxProfile
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

def main():
    parser = ArgumentParser()
    parser.add_argument("-p", "--pages", dest="pages", type=int, default=1,
                        help="how many pages of users to scrape (1 page = 24 users)")
    parser.add_argument("-d", "--delay", dest="delay", type=float, default=0.3,
                        help="delay in seconds between the user page requests")
    parser.add_argument("-db", "--database",
                        action="store_false", dest="db", default='users.db',
                        help="file path of the sqlite3 database")
    args = parser.parse_args()
    profile = FirefoxProfile()
    # Disable images
    profile.set_preference('permissions.default.image', 2)
    driver = Firefox(profile)
    login(driver)
    search(driver)
    user_urls = [time.sleep(args.delay) or url
                 for page in fetch_pages(driver, args.pages)
                 for url in fetch_users(page)]
    users = []
    for url in user_urls:
        try:
            users.append(get_user_data(driver, url))
        except Exception:
            traceback.print_exc()
            print('\nIgnoring exception (url=' + url + ')')
        time.sleep(args.delay)
    save_to_db(args.db, users)

def login(driver):
    login_url = 'https://myanimelist.net/login.php'
    driver.get(login_url)
    print("Please log into your Account manually.")
    WebDriverWait(driver, 600).until(EC.url_changes(login_url))

def search(driver):
    search_url = 'https://myanimelist.net/users.php'
    driver.get(search_url)
    print("Specify some search constraints and click 'Find user'.")
    WebDriverWait(driver, 600).until(EC.url_changes(search_url))
    time.sleep(3)

def fetch_pages(driver, page_count):
    yield driver.page_source
    for x in range(1, page_count):
        driver.get(driver.current_url + '&show=' + str(x * 24))
        yield driver.page_source

def fetch_users(page) -> List[str]:
    return re.findall(r'(?<=<div class="picSurround"><a href=").+?(?=">)', page)

User = namedtuple('User', ['name', 'last_online', 'gender', 'birthday', 'joined',
                           'location', 'shared', 'affinity', 'friend_count', 'days',
                           'mean_score', 'completed'])

def get_user_data(driver, url) -> User:
    url = 'https://myanimelist.net' + url
    driver.get(url)
    p = driver.page_source
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

def safe_re_search(*args, **kwargs) -> Optional[str]:
    match = re.search(*args, **kwargs)
    if match is None:
        return None
    return match.group(1)

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

def scrape_affinity(page):
    match = re.search(r'<div class="bar-outer-negative ar"><.*?>[-]?([-]?\d+\.*\d*)%'
                      r'.*?</span></div>\s*<div class="bar-outer-positive al"><.*?>.*?(\d+\.*\d*)%', page)
    if match:
        return float(match.group(1)) or float(match.group(2))

def safe_int(text: str) -> Optional[int]:
    if text is not None:
        return int(text.replace(',', ''))

def safe_float(text: str) -> Optional[float]:
    if text is not None:
        return float(text.replace(',', ''))

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
    main()
