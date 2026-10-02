import sys
import os
import xbmc


def _trace(msg):
    try:
        with open('/tmp/filma24_trace.log', 'a') as f:
            f.write(f"[{os.getpid()}] {msg}\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


def disable_core_dumps():
    """Prevents large core dumps from filling webOS flash storage on unexpected exits."""
    try:
        import ctypes

        class RLimit(ctypes.Structure):
            _fields_ = [('rlim_cur', ctypes.c_ulonglong), ('rlim_max', ctypes.c_ulonglong)]

        libc = ctypes.CDLL('libc.so.6')
        r = RLimit(0, 0)
        libc.setrlimit(4, ctypes.byref(r))  # RLIMIT_CORE = 4 on Linux
    except Exception:
        pass


def release_memory():
    """Forces Python garbage collection and releases glibc arena heap to the OS."""
    try:
        import gc
        gc.collect()
        import ctypes
        libc = ctypes.CDLL('libc.so.6')
        libc.malloc_trim(0)
    except Exception:
        pass


disable_core_dumps()
release_memory()

import concurrent.futures
_trace("imported concurrent.futures")
import html
import json
import re
import urllib.parse
_trace("imported basic modules")
import urllib3
_trace("imported urllib3")
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager
_trace("imported urllib3 components")
import requests
_trace("imported requests")
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
_trace("imported xbmc modules")

# Suppress insecure SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Addon metadata & handle setup
ADDON = xbmcaddon.Addon('plugin.video.filma24')
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

# Verified working Cloudflare Anycast edge IP for filma24.stream (bypasses ISP DNS blockade)
_DOH_IP = '188.114.97.7'


class CustomHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        extra_kw = {}
        if self.source_address:
            extra_kw['source_address'] = self.source_address
        if self.socket_options:
            extra_kw['socket_options'] = self.socket_options

        target_host = self.host
        try:
            base_netloc = urllib.parse.urlparse(get_base_url()).netloc
        except Exception:
            base_netloc = 'filma24.stream'

        if target_host in ('filma24.stream', 'www.filma24.stream', base_netloc):
            target_host = _DOH_IP

        return urllib3.util.connection.create_connection(
            (target_host, self.port), self.timeout, **extra_kw
        )


class CustomHTTPConnection(HTTPConnection):
    def _new_conn(self):
        extra_kw = {}
        if self.source_address:
            extra_kw['source_address'] = self.source_address
        if self.socket_options:
            extra_kw['socket_options'] = self.socket_options

        target_host = self.host
        try:
            base_netloc = urllib.parse.urlparse(get_base_url()).netloc
        except Exception:
            base_netloc = 'filma24.stream'

        if target_host in ('filma24.stream', 'www.filma24.stream', base_netloc):
            target_host = _DOH_IP

        return urllib3.util.connection.create_connection(
            (target_host, self.port), self.timeout, **extra_kw
        )


class CustomHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = CustomHTTPSConnection


class CustomHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = CustomHTTPConnection


class CustomPoolManager(PoolManager):
    def _new_pool(self, scheme, host, port, request_context=None):
        if scheme == 'https':
            return CustomHTTPSConnectionPool(host, port, **self.connection_pool_kw)
        elif scheme == 'http':
            return CustomHTTPConnectionPool(host, port, **self.connection_pool_kw)
        return super()._new_pool(scheme, host, port, request_context=request_context)


class CustomDNSAdapter(requests.adapters.HTTPAdapter):
    """Requests HTTPAdapter that routes filma24 domains to the bypass edge IP while preserving SNI."""
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = CustomPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )

# Arguments passed by Kodi runtime:
# sys.argv[0] -> Base plugin URL (e.g. 'plugin://plugin.video.filma24/')
# sys.argv[1] -> Routing directory handle integer as string (e.g. '1')
# sys.argv[2] -> Query parameter string (e.g. '?action=list_movies&page=1')
BASE_PLUGIN_URL = sys.argv[0]
HANDLE = int(sys.argv[1])

# Supported cyberlocker host domains for regex pattern matching
HOST_DOMAINS = [
    'vidmoly',
    'streamtape',
    'streamta',
    'voe',
    'bysesukior',
    'tuktukporn',
    'audiar',
    'reputationsdefend',
    'generatormind',
    'yugua',
    'jilliangoor',
    'doodstream',
    'dood',
    'ds2play',
    'mixdrop',
    'filemoon',
    'streamwish',
    'wishfast',
    'upstream',
    'vidsrc',
    'supervideo',
    'wolfstream',
    'lulustream',
    'filma.live',
    'eugenemakedraw'
]


def get_base_url() -> str:
    """Retrieve configured base domain from settings or default."""
    url = ADDON.getSetting('base_url')
    if not url:
        url = 'https://filma24.stream'
    return url.rstrip('/')


def get_user_agent() -> str:
    """Retrieve configured User-Agent from settings or modern Chrome desktop default."""
    ua = ADDON.getSetting('user_agent')
    if not ua:
        ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        )
    return ua


def get_timeout() -> int:
    """Retrieve network timeout setting in seconds."""
    timeout_str = ADDON.getSetting('timeout')
    try:
        val = int(timeout_str)
        return val if val > 0 else 15
    except (ValueError, TypeError):
        return 15


def get_ssl_verify() -> bool:
    """Retrieve SSL certificate verification setting (default False to allow mirrors with invalid certs)."""
    return ADDON.getSetting('ssl_verify').lower() == 'true'


def get_auto_select_server() -> bool:
    """Retrieve auto server selection setting."""
    return ADDON.getSetting('auto_select_server').lower() == 'true'


def get_doh_enabled() -> bool:
    """Retrieve DNS-over-HTTPS / ISP bypass setting."""
    try:
        return ADDON.getSetting('use_doh').lower() != 'false'
    except Exception:
        return True


def get_search_history() -> list:
    """Retrieves recent search queries from add-on userdata."""
    try:
        profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        hist_file = os.path.join(profile_dir, 'search_history.json')
        if not os.path.exists(hist_file):
            return []
        with open(hist_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_search_query(query: str):
    """Saves a search query to the recent search history list."""
    if not query:
        return
    try:
        profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir, exist_ok=True)
        hist_file = os.path.join(profile_dir, 'search_history.json')
        history = get_search_history()
        if query in history:
            history.remove(query)
        history.insert(0, query)
        history = history[:15]
        with open(hist_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
    except Exception:
        pass


def remove_search_item(query: str):
    """Removes a single query from the search history."""
    try:
        history = get_search_history()
        if query in history:
            history.remove(query)
            profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
            hist_file = os.path.join(profile_dir, 'search_history.json')
            with open(hist_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False)
    except Exception:
        pass
    xbmc.executebuiltin("Container.Refresh")


def clear_search_history():
    """Wipes all search history entries."""
    try:
        profile_dir = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        hist_file = os.path.join(profile_dir, 'search_history.json')
        if os.path.exists(hist_file):
            os.remove(hist_file)
    except Exception:
        pass
    xbmcgui.Dialog().notification(ADDON_NAME, "Historiku i kërkimit u fshi", xbmcgui.NOTIFICATION_INFO, 2000)
    xbmc.executebuiltin("Container.Refresh")


def get_http_session() -> requests.Session:
    """Create requests Session pre-configured with browser headers, referer, and SSL setting."""
    base_domain = get_base_url()
    session = requests.Session()
    if get_doh_enabled():
        adapter = CustomDNSAdapter()
        session.mount('https://', adapter)
        session.mount('http://', adapter)
    session.verify = get_ssl_verify()
    session.headers.update({
        'User-Agent': get_user_agent(),
        'Referer': f"{base_domain}/",
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,sq;q=0.8',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    })
    return session


def build_plugin_url(params: dict) -> str:
    """Construct full Kodi plugin URL from dictionary of query parameters."""
    return f"{BASE_PLUGIN_URL}?{urllib.parse.urlencode(params)}"


def apply_video_metadata(list_item: xbmcgui.ListItem, info: dict):
    """
    Applies video metadata using modern InfoTagVideo (Kodi 20/21/22)
    to eliminate deprecation warnings, falling back to setInfo for older builds.
    """
    if hasattr(list_item, 'getVideoInfoTag'):
        try:
            tag = list_item.getVideoInfoTag()
            if 'title' in info and hasattr(tag, 'setTitle') and info['title']:
                tag.setTitle(str(info['title']))
            if 'plot' in info and hasattr(tag, 'setPlot') and info['plot']:
                tag.setPlot(str(info['plot']))
            if 'year' in info and hasattr(tag, 'setYear') and info['year']:
                tag.setYear(int(info['year']))
            if 'mediatype' in info and hasattr(tag, 'setMediaType') and info['mediatype']:
                tag.setMediaType(str(info['mediatype']))
            if 'tvshowtitle' in info and hasattr(tag, 'setTvShowTitle') and info['tvshowtitle']:
                tag.setTvShowTitle(str(info['tvshowtitle']))
            if 'season' in info and hasattr(tag, 'setSeason') and info['season'] is not None:
                tag.setSeason(int(info['season']))
            if 'episode' in info and hasattr(tag, 'setEpisode') and info['episode'] is not None:
                tag.setEpisode(int(info['episode']))
            if 'rating' in info and hasattr(tag, 'setRating') and info['rating']:
                try:
                    tag.setRating(float(info['rating']))
                except Exception:
                    pass
            if 'genres' in info and hasattr(tag, 'setGenres') and info['genres']:
                try:
                    tag.setGenres(list(info['genres']))
                except Exception:
                    pass
            return
        except Exception:
            pass
    try:
        list_item.setInfo('video', info)
    except Exception:
        pass


def root_menu():
    """Renders main root folders on add-on launch."""
    xbmcplugin.setPluginCategory(HANDLE, ADDON_NAME)
    xbmcplugin.setContent(HANDLE, 'files')

    menu_items = [
        {
            'title': 'Filma të Fundit',
            'query': {'action': 'list_movies', 'content_type': 'movies', 'page': '1'},
            'icon': 'DefaultMovies.png'
        },
        {
            'title': 'Seriale',
            'query': {'action': 'list_movies', 'content_type': 'series', 'page': '1'},
            'icon': 'DefaultTVShows.png'
        },
        {
            'title': 'Kategori & Zhanre',
            'query': {'action': 'categories'},
            'icon': 'DefaultGenre.png'
        },
        {
            'title': 'Kërko',
            'query': {'action': 'search_menu'},
            'icon': 'DefaultAddonsSearch.png'
        },
        {
            'title': 'Cilësimet e Shtojcës',
            'query': {'action': 'open_settings'},
            'icon': 'DefaultAddonProgram.png'
        }
    ]

    for item in menu_items:
        list_item = xbmcgui.ListItem(label=item['title'])
        list_item.setArt({
            'icon': item['icon'],
            'thumb': item['icon']
        })
        url = build_plugin_url(item['query'])
        is_folder = item['query']['action'] != 'open_settings'
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def categories():
    """Renders list of movie genres and special categories."""
    xbmcplugin.setPluginCategory(HANDLE, "Kategori & Zhanre")
    xbmcplugin.setContent(HANDLE, 'files')
    base_domain = get_base_url()

    cats = [
        ('Aksion', f"{base_domain}/kategori/aksion", "Filma aksion me plot lëvizje."),
        ('Aventurë', f"{base_domain}/kategori/aventura", "Aventura fantastike dhe zbulime."),
        ('Animacion', f"{base_domain}/kategori/animuar", "Filma të animuar për të gjithë familjen."),
        ('Komedi', f"{base_domain}/kategori/komedi", "Filmat më gazmorë dhe komikë."),
        ('Krim', f"{base_domain}/kategori/krim", "Ngjarje të botës së krimit dhe hetime."),
        ('Dramë', f"{base_domain}/kategori/drame", "Histori prekëse dhe dramatike."),
        ('Fantazi', f"{base_domain}/kategori/fantazi", "Bota magjike dhe trillim shkencor."),
        ('Horror', f"{base_domain}/kategori/horror", "Filma të frikshëm dhe thriller mister."),
        ('Romancë', f"{base_domain}/kategori/romance", "Histori dashurie dhe ndjenja."),
        ('Thriller', f"{base_domain}/kategori/thriller", "Tension dhe pezull i lartë."),
        ('Dokumentar', f"{base_domain}/kategori/dokumentar", "Dokumentarë informues dhe edukues."),
        ('Të Dubluar Shqip', f"{base_domain}/kategori/dubluar", "Filma me dublim në gjuhën shqipe."),
        ('Filma Shqiptarë', f"{base_domain}/kategori/shqip", "Kinematografia shqiptare ndër vite."),
        ('Seriale Turke', f"{base_domain}/seriale-turke", "Serialet turke më të ndjekura me titra shqip.")
    ]

    for title, cat_url, plot in cats:
        list_item = xbmcgui.ListItem(label=title)
        list_item.setArt({
            'icon': 'DefaultGenre.png',
            'thumb': 'DefaultGenre.png'
        })
        apply_video_metadata(list_item, {'title': title, 'plot': plot})
        is_seriale = 'seriale' in cat_url
        url = build_plugin_url({
            'action': 'list_movies',
            'url': cat_url,
            'page': '1',
            'content_type': 'series' if is_seriale else 'movies'
        })
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def extract_movie_cards(html_content: str, base_url: str) -> list:
    """Ultra-fast regex-based card scraper that requires 0 dependencies and minimal memory."""
    cards = []
    card_pattern = re.compile(
        r'''(<(?:div|article)[^>]*class=[\"'][^\"']*(?:movie-thumb|item-movies|post|item)[^\"']*[\"'].*?)'''
        r'''(?=(?:<(?:div|article)[^>]*class=[\"'](?:movie-thumb|item-movies|post|item)|\Z))''',
        re.DOTALL | re.IGNORECASE
    )
    blocks = card_pattern.findall(html_content)
    if not blocks:
        blocks = re.findall(r'<article[^>]*>.*?</article>', html_content, re.DOTALL | re.IGNORECASE)

    seen_urls = set()
    for block in blocks:
        link_m = re.search(r'''<a[^>]+href=[\"']([^\"']+)[\"'][^>]+title=[\"']([^\"']+)[\"']''', block)
        if not link_m:
            link_m = re.search(r'''<a[^>]+title=[\"']([^\"']+)[\"'][^>]+href=[\"']([^\"']+)[\"']''', block)
        if not link_m:
            link_m = re.search(r'''<a[^>]+href=[\"']([^\"']+)[\"']''', block)
            if not link_m:
                continue
            item_url = link_m.group(1).strip()
            raw_title = 'Pa Titull'
        else:
            if 'title=' in link_m.group(0)[:link_m.group(0).find('href=')]:
                raw_title = html.unescape(link_m.group(1).strip())
                item_url = link_m.group(2).strip()
            else:
                item_url = link_m.group(1).strip()
                raw_title = html.unescape(link_m.group(2).strip())

        if not item_url or item_url.startswith('#') or item_url.startswith('javascript:'):
            continue
        if any(skip in item_url.lower() for skip in ['/zbulo', '/kategori', '/dmca', '/privacy', '/contact']):
            continue

        full_url = urllib.parse.urljoin(base_url, item_url)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title_h = re.search(r'''<(?:h4|h3|h2)[^>]*class=[\"']?[^\"'>]*?(?:post-title|title)?[^\"'>]*?>\s*(?:<a[^>]*>)?([^<]+)''', block, re.IGNORECASE)
        if title_h and title_h.group(1).strip() and not title_h.group(1).strip().isdigit():
            raw_title = html.unescape(title_h.group(1).strip())

        img_m = re.search(r'''<img[^>]+?\bsrc=[\"'](https?://[^\"']+)[\"']''', block)
        if not img_m:
            img_m = re.search(r'''<img[^>]+?(?:data-src|data-lazy-src)=[\"'](https?://[^\"']+)[\"']''', block)
        thumb_url = img_m.group(1).strip() if img_m else ''

        q_m = re.search(r'''class=[\"'](?:quality-poster|quality|featu|hd)[\"'][^>]*>([^<]+)<''', block, re.IGNORECASE)
        quality_badge = q_m.group(1).strip() if q_m else ''

        r_m = re.search(r'''class=[\"'](?:imdb-poster|imdb|rating)[\"'][^>]*>([^<]+)<''', block, re.IGNORECASE)
        rating_val = None
        if r_m:
            num_m = re.search(r'(\d+(?:\.\d+)?)', r_m.group(1))
            if num_m:
                try:
                    rating_val = float(num_m.group(1))
                except ValueError:
                    pass

        y_m = re.search(r'\b(19\d\d|20\d\d)\b', block)
        year_val = int(y_m.group(1)) if y_m else None

        p_m = re.search(r'''<p[^>]*class=[\"'](?:f-desc|texto|plot)[\"'][^>]*>(.*?)</p>''', block, re.DOTALL | re.IGNORECASE)
        plot_text = html.unescape(re.sub(r'<[^>]+>', '', p_m.group(1)).strip()) if p_m else ''

        genres_m = re.findall(r'''<a[^>]+class=[\"'](?:text-dark|genre)[\"'][^>]*>([^<]+)</a>''', block)
        if not genres_m:
            genres_m = re.findall(r'''<span class=[\"']m-card-genre[\"']>([^<]+)</span>''', block)
        genres = [html.unescape(g.strip()) for g in genres_m if g.strip()]

        cards.append({
            'title': raw_title,
            'url': full_url,
            'thumb': thumb_url,
            'quality': quality_badge,
            'rating': rating_val,
            'year': year_val,
            'plot': plot_text,
            'genres': genres
        })
    return cards


def extract_next_page(html_content: str, current_page: int, base_url: str) -> str:
    """Finds next page link from pagination markup."""
    next_m = re.search(r'''<a[^>]+class=[\"']([^\"']*nextpostslink[^\"']*)[\"'][^>]+href=[\"']([^\"']+)[\"']''', html_content, re.IGNORECASE)
    if not next_m:
        next_m = re.search(r'''<a[^>]+href=[\"']([^\"']+)[\"'][^>]+class=[\"']([^\"']*nextpostslink[^\"']*)[\"']''', html_content, re.IGNORECASE)
        if next_m:
            return urllib.parse.urljoin(base_url, next_m.group(1).strip())
    else:
        return urllib.parse.urljoin(base_url, next_m.group(2).strip())
    if not next_m:
        next_m = re.search(r'''<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>\s*''' + str(current_page + 1) + r'''\s*<''', html_content)
        if next_m:
            return urllib.parse.urljoin(base_url, next_m.group(1).strip())
    return ''


def list_movies(url: str, page: str, content_type: str, query: str = ''):
    """
    Fetches catalog pages, extracts movie cards via multi-selector parsing,
    populates Kodi virtual directory, and handles pagination.
    """
    base_domain = get_base_url()
    page_num = int(page) if page and page.isdigit() else 1

    # Formulate destination URL if not directly passed
    if not url:
        if content_type == 'series':
            if page_num > 1:
                url = f"{base_domain}/seriale/page/{page_num}/"
            else:
                url = f"{base_domain}/seriale"
            category_label = f"Seriale (Faqja {page_num})"
        elif content_type == 'search':
            category_label = f"Kërkim: {query} (Faqja {page_num})"
        else:
            if page_num > 1:
                url = f"{base_domain}/page/{page_num}/"
            else:
                url = f"{base_domain}/"
            category_label = f"Filma të Fundit (Faqja {page_num})"
    else:
        category_label = f"Katalogu (Faqja {page_num})"

    xbmc.log(f"[{ADDON_NAME}] list_movies starting: url='{url}', content_type='{content_type}', page={page_num}", level=xbmc.LOGINFO)

    xbmcplugin.setPluginCategory(HANDLE, category_label)
    xbmcplugin.setContent(HANDLE, 'tvshows' if content_type == 'series' else 'movies')

    session = get_http_session()
    movie_cards = []
    has_next_page = False
    next_page_url = None

    if content_type == 'search' and query:
        safe_query = urllib.parse.quote_plus(query)
        search_types = ['movie', 'seriale']
        has_more_flag = False

        def _fetch_search_type(stype):
            endpoint = f"{base_domain}/wp-zcore/discover.php?type={stype}&q={safe_query}&page={page_num}"
            try:
                r = session.get(endpoint, timeout=get_timeout(), headers={'X-Requested-With': 'XMLHttpRequest'})
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                xbmc.log(f"[{ADDON_NAME}] Search error for {stype}: {e}", level=xbmc.LOGWARNING)
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            results = ex.map(_fetch_search_type, search_types)
            for res_json in results:
                if not res_json:
                    continue
                if res_json.get('hasMore'):
                    has_more_flag = True
                for it in res_json.get('items', []):
                    rel_url = it.get('u', '')
                    if not rel_url:
                        continue
                    full_u = urllib.parse.urljoin(base_domain, rel_url)
                    movie_cards.append({
                        'title': html.unescape(it.get('t', 'Pa Titull')),
                        'url': full_u,
                        'thumb': it.get('p', ''),
                        'quality': it.get('q', ''),
                        'rating': float(it['r']) if it.get('r') else None,
                        'year': int(it['y']) if it.get('y') and str(it['y']).isdigit() else None,
                        'plot': '',
                        'genres': [it['g']] if it.get('g') else []
                    })

        has_next_page = has_more_flag
        if has_next_page:
            next_page_url = build_plugin_url({
                'action': 'list_movies',
                'content_type': 'search',
                'query': query,
                'page': str(page_num + 1)
            })
    else:
        try:
            xbmc.log(f"[{ADDON_NAME}] HTTP GET requesting: {url}", level=xbmc.LOGINFO)
            response = session.get(url, timeout=get_timeout())
            response.raise_for_status()
            html_content = response.text
            xbmc.log(f"[{ADDON_NAME}] HTTP GET received: {response.status_code}, length {len(html_content)} bytes", level=xbmc.LOGINFO)
        except requests.RequestException as exc:
            xbmc.log(f"[{ADDON_NAME}] Connection error fetching {url}: {exc}", level=xbmc.LOGERROR)
            xbmcgui.Dialog().notification(ADDON_NAME, "Gabim në lidhje me faqen", xbmcgui.NOTIFICATION_ERROR, 3500)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

        movie_cards = extract_movie_cards(html_content, base_domain)
        next_extracted = extract_next_page(html_content, page_num, base_domain)
        if next_extracted:
            has_next_page = True
            next_page_url = next_extracted

    xbmc.log(f"[{ADDON_NAME}] Found {len(movie_cards)} cards on page", level=xbmc.LOGINFO)

    for item in movie_cards:
        raw_title = item['title']
        item_page_url = item['url']
        thumb_url = item['thumb']
        quality_badge = item['quality']
        display_title = f"{raw_title} [{quality_badge}]" if quality_badge else raw_title

        list_item = xbmcgui.ListItem(label=display_title)
        list_item.setArt({
            'icon': thumb_url or 'DefaultVideo.png',
            'thumb': thumb_url or 'DefaultVideo.png',
            'poster': thumb_url or 'DefaultVideo.png'
        })

        is_item_series = (content_type == 'series') or ('/seriale/' in item_page_url)
        info_dict = {
            'title': raw_title,
            'mediatype': 'tvshow' if is_item_series else 'movie'
        }
        if item['year']:
            info_dict['year'] = item['year']
        if item['rating'] is not None:
            info_dict['rating'] = item['rating']
        if item['plot']:
            info_dict['plot'] = item['plot']
        if item['genres']:
            info_dict['genres'] = item['genres']

        apply_video_metadata(list_item, info_dict)

        context_items = [
            ("Cilësimet e Shtojcës", f"RunPlugin({build_plugin_url({'action': 'open_settings'})})"),
            ("Rifresko", "Container.Refresh")
        ]
        list_item.addContextMenuItems(context_items)

        if is_item_series:
            series_callback_url = build_plugin_url({
                'action': 'list_episodes',
                'url': item_page_url,
                'thumb': thumb_url,
                'title': raw_title
            })
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=series_callback_url, listitem=list_item, isFolder=True)
        else:
            list_item.setProperty('IsPlayable', 'true')
            play_callback_url = build_plugin_url({
                'action': 'play',
                'url': item_page_url
            })
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=play_callback_url, listitem=list_item, isFolder=False)

    if has_next_page and next_page_url:
        next_folder_item = xbmcgui.ListItem(label="Faqja Tjetër >>")
        next_folder_item.setArt({
            'icon': 'DefaultFolder.png',
            'thumb': 'DefaultFolder.png'
        })
        if content_type == 'search':
            next_callback_url = next_page_url
        else:
            next_callback_url = build_plugin_url({
                'action': 'list_movies',
                'url': next_page_url,
                'page': str(page_num + 1),
                'content_type': content_type,
                'query': query
            })
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=next_callback_url, listitem=next_folder_item, isFolder=True)

    xbmc.log(f"[{ADDON_NAME}] Finished processing directory items. Calling endOfDirectory...", level=xbmc.LOGINFO)
    xbmcplugin.endOfDirectory(HANDLE)
    release_memory()


def list_episodes(series_url: str, series_thumb: str = '', series_title: str = ''):
    """
    Fetches the series page, scrapes episode cards from DooPlay #seasons containers,
    and populates Kodi with playable episode items.
    """
    xbmcplugin.setPluginCategory(HANDLE, series_title or "Episodet")
    xbmcplugin.setContent(HANDLE, 'episodes')

    session = get_http_session()
    try:
        response = session.get(series_url, timeout=get_timeout())
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as exc:
        xbmc.log(f"[{ADDON_NAME}] Error fetching series episodes: {exc}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(ADDON_NAME, "Gabim në ngarkimin e episodeve", xbmcgui.NOTIFICATION_ERROR, 3500)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # 1. Check if page contains Seasons (only if not already on a specific season page)
    season_links = []
    if '/sezoni-' not in series_url:
        seen_seasons = set()
        for m in re.finditer(r'''<a[^>]+href=[\"']([^\"']*/sezoni-[^\"']*)[\"'][^>]*>(.*?)</a>''', html_content, re.DOTALL | re.IGNORECASE):
            s_url = urllib.parse.urljoin(series_url, m.group(1).strip())
            if s_url not in seen_seasons:
                seen_seasons.add(s_url)
                s_raw = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2)).strip())
                match = re.search(r'(Sezoni\s*\d+)', s_raw, re.IGNORECASE)
                display_title = match.group(1) if match else (s_raw or f"Sezoni {len(seen_seasons)}")
                season_links.append((display_title, s_url))

    if season_links:
        xbmcplugin.setPluginCategory(HANDLE, series_title or "Sezonet")
        xbmcplugin.setContent(HANDLE, 'seasons')
        for s_title, s_url in season_links:
            list_item = xbmcgui.ListItem(label=s_title)
            list_item.setArt({
                'icon': series_thumb or 'DefaultFolder.png',
                'thumb': series_thumb or 'DefaultFolder.png',
                'poster': series_thumb or 'DefaultFolder.png'
            })
            apply_video_metadata(list_item, {'title': s_title, 'tvshowtitle': series_title, 'mediatype': 'season'})
            list_item.addContextMenuItems([
                ("Cilësimet e Shtojcës", f"RunPlugin({build_plugin_url({'action': 'open_settings'})})"),
                ("Rifresko", "Container.Refresh")
            ])
            call_url = build_plugin_url({
                'action': 'list_episodes',
                'url': s_url,
                'thumb': series_thumb,
                'title': f"{series_title} - {s_title}"
            })
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=call_url, listitem=list_item, isFolder=True)
        xbmcplugin.endOfDirectory(HANDLE)
        release_memory()
        return

    # 2. Extract episodes (e.g. /seria/ links or DooPlay episode cards)
    xbmcplugin.setPluginCategory(HANDLE, series_title or "Episodet")
    xbmcplugin.setContent(HANDLE, 'episodes')

    episode_links = []
    seen_episodes = set()
    for m in re.finditer(r'''<a[^>]+href=[\"']([^\"']*/seria/[^\"']+)[\"'][^>]*>(.*?)</a>''', html_content, re.DOTALL | re.IGNORECASE):
        ep_url = urllib.parse.urljoin(series_url, m.group(1).strip())
        if ep_url not in seen_episodes:
            seen_episodes.add(ep_url)
            ep_title = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2)).strip())
            ep_title = ' '.join(ep_title.split())
            if any(skip in ep_title.lower() for skip in ['fillo nga', 'episodi i fundit']):
                continue
            episode_links.append((ep_title or 'Episod', ep_url))

    # If standard DooPlay episode cards exist (#seasons .episodios li)
    if not episode_links:
        for ep_m in re.finditer(r'''<li[^>]*>.*?<div class=[\"']episodiotitle[\"']>.*?<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>''', html_content, re.DOTALL | re.IGNORECASE):
            ep_url = urllib.parse.urljoin(series_url, ep_m.group(1).strip())
            if ep_url not in seen_episodes:
                seen_episodes.add(ep_url)
                ep_title = html.unescape(re.sub(r'<[^>]+>', ' ', ep_m.group(2)).strip())
                ep_title = ' '.join(ep_title.split())
                episode_links.append((ep_title or 'Episod', ep_url))

    if not episode_links:
        # Fallback to direct player check
        play(series_url)
        return

    for ep_title, ep_url in episode_links:
        list_item = xbmcgui.ListItem(label=ep_title)
        list_item.setArt({
            'icon': series_thumb or 'DefaultVideo.png',
            'thumb': series_thumb or 'DefaultVideo.png',
            'poster': series_thumb or 'DefaultVideo.png'
        })
        info_dict = {
            'title': ep_title,
            'tvshowtitle': series_title,
            'mediatype': 'episode'
        }
        match = re.search(r'[eE](\d+)', ep_title)
        if match:
            info_dict['episode'] = int(match.group(1))

        apply_video_metadata(list_item, info_dict)
        list_item.setProperty('IsPlayable', 'true')
        list_item.addContextMenuItems([
            ("Cilësimet e Shtojcës", f"RunPlugin({build_plugin_url({'action': 'open_settings'})})"),
            ("Rifresko", "Container.Refresh")
        ])
        call_url = build_plugin_url({'action': 'play', 'url': ep_url})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=call_url, listitem=list_item, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def search_menu():
    """Renders search interface displaying recent queries and new search prompt."""
    xbmcplugin.setPluginCategory(HANDLE, "Kërko")
    xbmcplugin.setContent(HANDLE, 'files')

    # Option to initiate a new search
    new_search_item = xbmcgui.ListItem(label="[+] Kërkim i Ri...")
    new_search_item.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': 'DefaultAddonsSearch.png'})
    apply_video_metadata(new_search_item, {'title': '[+] Kërkim i Ri...', 'plot': 'Kërkoni filma ose seriale në Filma24.'})
    new_url = build_plugin_url({'action': 'search_prompt'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=new_url, listitem=new_search_item, isFolder=True)

    # Render previous search history
    history = get_search_history()
    for term in history:
        hist_item = xbmcgui.ListItem(label=f"  {term}")
        hist_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        apply_video_metadata(hist_item, {'title': term, 'plot': f"Rezultatet e kërkimit për '{term}'"})
        url = build_plugin_url({
            'action': 'list_movies',
            'content_type': 'search',
            'query': term,
            'page': '1'
        })
        hist_item.addContextMenuItems([
            ("Fshi nga Historiku", f"RunPlugin({build_plugin_url({'action': 'remove_search_item', 'query': term})})"),
            ("Pastro të Gjithë Historikun", f"RunPlugin({build_plugin_url({'action': 'clear_search_history'})})")
        ])
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=hist_item, isFolder=True)

    # Option to wipe history if entries exist
    if history:
        clear_item = xbmcgui.ListItem(label="[-] Pastro Historikun e Kërkimeve")
        clear_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        apply_video_metadata(clear_item, {'title': 'Pastro Historikun', 'plot': 'Fshin të gjithë termat e ruajtur të kërkimit.'})
        clear_url = build_plugin_url({'action': 'clear_search_history'})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=clear_url, listitem=clear_item, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def search_prompt():
    """Opens native on-screen keyboard, saves term to history, and runs movie listing."""
    keyboard = xbmc.Keyboard('', 'Kërko Filma ose Seriale')
    keyboard.doModal()

    if keyboard.isConfirmed():
        search_term = keyboard.getText().strip()
        if search_term:
            save_search_query(search_term)
            list_movies(url='', page='1', content_type='search', query=search_term)
            return

    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def clean_embed_url(raw_url: str) -> str:
    """Normalize extracted embed URLs."""
    cleaned = html.unescape(raw_url).replace(r'\/', '/').replace('\\/', '/').strip('\'" ')
    if cleaned.startswith('//'):
        cleaned = f"https:{cleaned}"
    return cleaned


def extract_server_name(embed_url: str) -> str:
    """Identify host provider name from URL domain for display labels."""
    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', embed_url, re.IGNORECASE)
    if domain_match:
        domain = domain_match.group(1).lower()
        if 'vidmoly' in domain:
            return 'Vidmoly'
        if any(v in domain for v in ['voe', 'bysesukior', 'tuktukporn', 'yugua', 'audiar', 'reputationsdefend', 'generatormind', 'jilliangoor', 'eugenemakedraw']):
            return 'VOE'
        if 'streamtape' in domain or 'streamta' in domain:
            return 'Streamtape'
        if 'dood' in domain or 'ds2play' in domain:
            return 'Doodstream'
        if 'mixdrop' in domain:
            return 'Mixdrop'
        if 'filemoon' in domain:
            return 'Filemoon'
        if 'streamwish' in domain or 'wish' in domain:
            return 'Streamwish'
        if 'upstream' in domain:
            return 'Upstream'
        if 'lulustream' in domain:
            return 'Lulustream'
        if 'filma.live' in domain:
            return 'FilmaLive'
        for known_host in HOST_DOMAINS:
            if known_host in domain:
                return known_host.capitalize()
        return domain
    return 'Unknown Server'


def extract_embed_sources(movie_url: str, html_content: str, session: requests.Session) -> list:
    """
    Extracts all third-party video iframe embeds from player containers,
    server tabs, DooPlay AJAX player endpoints, and regex host patterns.
    Uses ThreadPoolExecutor for concurrent retrieval of server tabs.
    """
    found_sources = []
    seen_embeds = set()

    def add_source(source_url: str, label_hint: str = ''):
        url_normalized = clean_embed_url(source_url)
        if not url_normalized.startswith('http'):
            return
        if url_normalized in seen_embeds:
            return

        # Filter out obvious non-video or trailer embeds (trackers, ads, youtube trailers)
        blacklisted = ['facebook.com', 'google.com', 'twitter.com', 'recaptcha', 'disqus', 'analytics', 'youtube.com', 'youtu.be']
        if any(b in url_normalized.lower() for b in blacklisted):
            return

        seen_embeds.add(url_normalized)
        host_detected = extract_server_name(url_normalized)
        if label_hint:
            if host_detected.lower() in label_hint.lower():
                display_name = label_hint
            else:
                display_name = f"{label_hint} ({host_detected})"
        else:
            display_name = host_detected

        found_sources.append({
            'url': url_normalized,
            'name': display_name
        })

    # Detect active server tab label if present
    active_m = re.search(r'''<(?:a|li)[^>]+class=[\"']([^\"']*(?:servers-list|server-item)[^\"']*active[^\"']*)[\"'][^>]*>(.*?)<''', html_content, re.IGNORECASE)
    active_label = html.unescape(re.sub(r'<[^>]+>', '', active_m.group(2)).strip()) if (active_m and active_m.group(2)) else ''

    # 1. Search page markup for iframe elements
    for ifr_m in re.finditer(r'''<iframe[^>]+(?:src|data-src|data-lazy-src|data-url)=[\"']([^\"']+)[\"']''', html_content, re.IGNORECASE):
        add_source(ifr_m.group(1), active_label)

    # 2. Parallel scraping of non-active Server Tabs and DooPlay AJAX endpoints
    servers_list = []
    for tab_m in re.finditer(r'''<a[^>]+href=[\"']([^\"']*(?:server=|\?srv=)[^\"']*)[\"'][^>]*>(.*?)</a>''', html_content, re.IGNORECASE):
        if 'active' not in tab_m.group(0):
            srv_url = urllib.parse.urljoin(movie_url, tab_m.group(1).strip())
            srv_label = html.unescape(re.sub(r'<[^>]+>', '', tab_m.group(2)).strip()) or 'Server'
            servers_list.append((srv_url, srv_label))

    ajax_options = []
    for opt_m in re.finditer(r'''<li[^>]+class=[\"']([^\"']*dooplay_player_option[^\"']*)[\"'][^>]+data-post=[\"'](\d+)[\"'][^>]+data-nume=[\"'](\d+)[\"'][^>]+data-type=[\"']([^\"']+)[\"'][^>]*>(.*?)</li>''', html_content, re.IGNORECASE):
        opt_post = opt_m.group(2)
        opt_nume = opt_m.group(3)
        opt_type = opt_m.group(4)
        opt_label = html.unescape(re.sub(r'<[^>]+>', '', opt_m.group(5)).strip()) or f"Server {opt_nume}"
        ajax_options.append((opt_post, opt_nume, opt_type, opt_label))

    base_domain = get_base_url()
    ajax_endpoint = f"{base_domain}/wp-admin/admin-ajax.php"

    def _fetch_server_tab(srv_url: str, srv_label: str):
        results = []
        try:
            srv_resp = session.get(srv_url, timeout=get_timeout())
            if srv_resp.status_code == 200:
                for ifr_m in re.finditer(r'''<iframe[^>]+(?:src|data-src|data-lazy-src)=[\"']([^\"']+)[\"']''', srv_resp.text, re.IGNORECASE):
                    results.append((ifr_m.group(1), srv_label))
        except Exception:
            pass
        return results

    def _fetch_ajax_player(post_id: str, nume: str, ptype: str, label: str):
        results = []
        try:
            payload = {
                'action': 'doo_player_ajax',
                'post': post_id,
                'nume': nume,
                'type': ptype
            }
            ajax_resp = session.post(
                ajax_endpoint,
                data=payload,
                timeout=get_timeout(),
                headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': movie_url}
            )
            if ajax_resp.status_code == 200:
                resp_data = ajax_resp.text
                for matched_iframe in re.findall(r'''<iframe[^>]+src=[\"']([^\"']+)[\"']''', resp_data, re.IGNORECASE):
                    results.append((matched_iframe, label))
                host_regex_pattern = r'https?://(?:www\.)?(?:' + '|'.join(HOST_DOMAINS) + r')[^\s"\'<>]+'
                for matched_url in re.findall(host_regex_pattern, resp_data, re.IGNORECASE):
                    results.append((matched_url, label))
        except Exception:
            pass
        return results

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for srv_url, srv_label in servers_list:
            tasks.append(executor.submit(_fetch_server_tab, srv_url, srv_label))

        for post_id, nume, ptype, label in ajax_options:
            tasks.append(executor.submit(_fetch_ajax_player, post_id, nume, ptype, label))

        for future in concurrent.futures.as_completed(tasks):
            try:
                for src_url, s_label in future.result():
                    add_source(src_url, s_label)
            except Exception:
                pass

    # 3. Regex matches across entire page markup for known host patterns as fallback
    host_regex_pattern = r'https?://(?:www\.)?(?:' + '|'.join(HOST_DOMAINS) + r')[^\s"\'<>]+'
    for match in re.findall(host_regex_pattern, html_content, re.IGNORECASE):
        add_source(match)

    return found_sources


def resolve_and_play(chosen_source: dict) -> bool:
    """
    Attempts to resolve and start playback for a chosen video source.
    Returns True if resolved and handed over to Kodi, False otherwise.
    """
    chosen_url = chosen_source['url']
    source_name = chosen_source.get('name', 'Server')

    # Direct stream check (.m3u8, .mp4)
    if re.search(r'\.(?:m3u8|mp4)(?:\?|$)', chosen_url, re.IGNORECASE):
        stream_url = chosen_url
        if '|' not in stream_url:
            stream_url += f"|User-Agent={urllib.parse.quote(get_user_agent())}&Referer={urllib.parse.quote(get_base_url())}/"
        play_item = xbmcgui.ListItem(path=stream_url)
        play_item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)
        return True

    # Import resolveurl
    try:
        import resolveurl
    except ImportError:
        xbmc.log(f"[{ADDON_NAME}] ResolveURL module is missing.", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(ADDON_NAME, "Moduli script.module.resolveurl nuk është instaluar", xbmcgui.NOTIFICATION_ERROR, 4000)
        return False

    # Check if host is valid
    if not resolveurl.HostedMediaFile(chosen_url).valid_url():
        xbmc.log(f"[{ADDON_NAME}] Unsupported video host URL: {chosen_url}", level=xbmc.LOGWARNING)
        return False

    # Resolve direct stream URL with progress dialog
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create(ADDON_NAME, f"Duke lidhur me {source_name}...")

    direct_stream_url = None
    try:
        direct_stream_url = resolveurl.resolve(chosen_url)
    except Exception as exc:
        xbmc.log(f"[{ADDON_NAME}] Error resolving {chosen_url}: {exc}", level=xbmc.LOGERROR)
    finally:
        progress_dialog.close()

    if direct_stream_url:
        play_item = xbmcgui.ListItem(path=direct_stream_url)
        play_item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)
        return True

    return False


def play(movie_url: str):
    """
    Fetches the movie page, discovers embeds, resolves the stream with ResolveURL,
    and hands over playback to Kodi with retry and auto-select support.
    """
    if not movie_url:
        xbmcgui.Dialog().notification(ADDON_NAME, "URL e filmit mungon", xbmcgui.NOTIFICATION_ERROR, 3000)
        xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
        return

    session = get_http_session()
    try:
        response = session.get(movie_url, timeout=get_timeout())
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as exc:
        xbmc.log(f"[{ADDON_NAME}] Connection error fetching movie page {movie_url}: {exc}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification(ADDON_NAME, "Gabim në lidhje me faqen e filmit", xbmcgui.NOTIFICATION_ERROR, 3500)
        xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
        return

    # Extract all third-party embeds
    sources = extract_embed_sources(movie_url, html_content, session)
    if not sources:
        xbmcgui.Dialog().notification(ADDON_NAME, "Nuk u gjet asnjë server videoje për këtë film", xbmcgui.NOTIFICATION_WARNING, 3500)
        xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
        return

    # Auto-select server mode
    if get_auto_select_server():
        for src in sources:
            if resolve_and_play(src):
                return
        xbmcgui.Dialog().notification(ADDON_NAME, "Asnjë server nuk mund të hapej automatikisht", xbmcgui.NOTIFICATION_ERROR, 3500)
        xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
        return

    # Manual server selection mode with retry on failure
    while sources:
        if len(sources) > 1:
            menu_labels = [f"Server {idx + 1}: {src['name']}" for idx, src in enumerate(sources)]
            selection = xbmcgui.Dialog().select("Zgjidhni Serverin", menu_labels)
            if selection < 0:
                # User dismissed the modal dialog
                xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
                return
            selected_source = sources[selection]
        else:
            selected_source = sources[0]

        if resolve_and_play(selected_source):
            return

        # Playback failed on chosen source
        sources.remove(selected_source)
        if sources:
            retry = xbmcgui.Dialog().yesno(
                ADDON_NAME,
                f"Serveri '{selected_source['name']}' nuk mund të hapej.\nDëshironi të provoni një server tjetër?"
            )
            if not retry:
                break
        else:
            xbmcgui.Dialog().notification(ADDON_NAME, "Zgjidhja e videos dështoi nga të gjithë serverët", xbmcgui.NOTIFICATION_ERROR, 3500)

    xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())


def router():
    """URL query string dispatcher."""
    xbmc.log(f"[{ADDON_NAME}] router dispatching: sys.argv={sys.argv}", level=xbmc.LOGINFO)
    try:
        raw_query = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith('?') else ''
        parsed_params = urllib.parse.parse_qs(raw_query)
        params = {k: v[0] if len(v) == 1 else v for k, v in parsed_params.items()}

        action = params.get('action')

        if not action:
            root_menu()
        elif action == 'list_movies':
            list_movies(
                url=params.get('url', ''),
                page=params.get('page', '1'),
                content_type=params.get('content_type', 'movies'),
                query=params.get('query', '')
            )
        elif action == 'list_episodes':
            list_episodes(
                series_url=params.get('url', ''),
                series_thumb=params.get('thumb', ''),
                series_title=params.get('title', '')
            )
        elif action == 'categories':
            categories()
        elif action == 'search_menu':
            search_menu()
        elif action == 'search_prompt' or action == 'search':
            search_prompt()
        elif action == 'remove_search_item':
            remove_search_item(query=params.get('query', ''))
        elif action == 'clear_search_history':
            clear_search_history()
        elif action == 'open_settings':
            ADDON.openSettings()
        elif action == 'play':
            play(movie_url=params.get('url', ''))
        else:
            xbmc.log(f"[{ADDON_NAME}] Invalid action dispatched: {action}", level=xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
    except Exception as exc:
        xbmc.log(f"[{ADDON_NAME}] Unhandled exception in router: {exc}", level=xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), level=xbmc.LOGERROR)
        try:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        except Exception:
            pass
    finally:
        release_memory()


if __name__ == '__main__':
    router()
