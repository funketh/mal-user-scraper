# MyAnimeList.net User Scraper
Scrapes information from myanimelist.net profile pages and saves it into an sqlite3 database.
# Disclaimer
This is an inofficial script so you could get banned if you scrape to many pages of users because the script is very fast.
Use at your own risk!
# Requirements
* Python version 3.7
* `aiohttp` library
* A myanimelist.net account
* (Probably) some way to view the sqlite3 database (I recommend [DB Browser for SQLite](https://sqlitebrowser.org/))
# Instructions
1. Run `python3.7 mal_user_scraper.py` (for command line arguments, view below)
2. Input your username and password when asked
# Command Line Arguments
```
usage: mal_user_scraper.py [-h] [-n NAME] [-o OLDER] [-y YOUNGER]
                           [-l LOCATION] [-g GENDER] [-p PAGES] [-d DELAY]
                           [-db]

optional arguments:
  -h, --help            show this help message and exit
  -n NAME, --name NAME  found users names must match this
  -o OLDER, --older OLDER
                        found users must be older than this (in years)
  -y YOUNGER, --younger YOUNGER
                        found users must be younger than this (in years)
  -l LOCATION, --location LOCATION
                        found users must live here
  -g GENDER, --gender GENDER
                        found users must be of this gender_id (0=irrelevant,
                        1=male, 2=female, 3=non-binary}
  -p PAGES, --pages PAGES
                        how many pages of users to scrape (1 page = 24 users)
  -d DELAY, --delay DELAY
                        delay in seconds between the user page requests
  -db, --database       file path of the sqlite3 database
```
# To-Do
* favorite anime
