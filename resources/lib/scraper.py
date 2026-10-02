# -*- coding: utf-8 -*-
"""
Web scraper module for Filma24 using requests and BeautifulSoup4.
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

BASE_URL = "https://www.filma24.to"  # Replace with actual mirror/target domain


class Filma24Scraper:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 15):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.timeout = timeout

    def fetch_soup(self, url: str) -> BeautifulSoup:
        """Fetch HTML content and return parsed BeautifulSoup object."""
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')

    def get_latest_movies(self, page: int = 1) -> list:
        """
        Scrapes list of latest movies.
        Returns list of dicts: [{'title': str, 'url': str, 'thumb': str, 'year': str, 'plot': str}]
        """
        target_url = f"{self.base_url}/page/{page}" if page > 1 else self.base_url
        soup = self.fetch_soup(target_url)
        movies = []

        # Example selector pattern - adjust according to the target website DOM
        for item in soup.select('div.movie-item, article.item'):
            title_elem = item.select_one('.title a, h2 a')
            img_elem = item.select_one('img')
            if title_elem:
                movies.append({
                    'title': title_elem.get_text(strip=True),
                    'url': title_elem.get('href'),
                    'thumb': img_elem.get('src') if img_elem else '',
                    'plot': item.select_one('.plot, .desc').get_text(strip=True) if item.select_one('.plot, .desc') else ''
                })
        return movies

    def search_movies(self, query: str) -> list:
        """Searches movies by query term."""
        search_url = f"{self.base_url}/?s={requests.utils.quote(query)}"
        soup = self.fetch_soup(search_url)
        # Parse search results similarly
        return []
