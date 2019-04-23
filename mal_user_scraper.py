# NOTE: This script only scrapes Anime related data
import time
from collections import namedtuple

import re
import sqlite3
from datetime import datetime, timedelta
from selenium.webdriver import Firefox
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from typing import Optional, List

# Each page contains 24 users
USER_PAGES = 67
# Delay in seconds between the individual user page requests
# Decreasing this increases the speed of the script but puts a higher load on the MAL servers
DELAY = 0.3
DATABASE_FILENAME = 'users.db'

def main():
    driver = Firefox()
    login(driver)
    search(driver)
    user_urls = [time.sleep(DELAY) or url
                 for page in fetch_pages(driver)
                 for url in fetch_users(page)]
    users = [time.sleep(DELAY) or get_user_data(driver, url)
             for url in user_urls]
    save_to_db(users)

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

def fetch_pages(driver):
    yield driver.page_source
    for x in range(1, USER_PAGES):
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
        joined=to_date(mal_to_datetime(safe_re_search(r'Joined</span><span class="user-status-data di-ib fl-r">(.*?)<', p))),
        shared=int(safe_re_search(r'class="fs11">(\d+?) Shared', p)),
        affinity=scrape_affinity(p),
        friend_count=int(safe_re_search(r'All \((\d+?)\)</a>Friends</h4>', p)),
        days=float(safe_re_search(r'Anime Stats</h5>\s*<.*?>\s*<.*?><.*?>Days: </span>(\d+\.*\d*)</div>', p)),
        mean_score=float(safe_re_search(r'Anime Stats</h5>\s*<.*?>\s*<.*?><.*?>.*?<.*?>.*?<.*?>\s*<.*?><.*?>'
                                        r'Mean Score: </span>(\d+\.*\d*)', p)),
        completed=int(safe_re_search(r'Completed</a><span class="di-ib fl-r lh10">(\d+)', p)),
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

def save_to_db(users):
    db = sqlite3.connect(DATABASE_FILENAME)
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
