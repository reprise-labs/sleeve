#!/usr/bin/env python3
"""Ophalen van Discogs: één keer per adres, onthouden, en opnieuw proberen als Discogs even nee zegt.

Feiten:
  - Discogs staat zonder account ±25 aanvragen per minuut toe (antwoord 429 als het er meer zijn);
  - elk onderdeel van een release vraagt dezelfde gegevens en foto's op.
Dus: wat al opgehaald is, komt uit het geheugen (een map met bestanden, gedeeld door alle
onderdelen die tegelijk lopen), en een 429 of een storing aan de kant van Discogs is geen
reden om een onderdeel te laten mislukken: even wachten en opnieuw.

De map: SLEEVE_NET_CACHE (de bridge zet die op de taakmap), anders een map in de tijdelijke map.
"""
import hashlib, os, subprocess, tempfile, time, urllib.error, urllib.request

UA = 'Sleeve/0.3.1'
TTL = 3600                       # zo lang (s) geldt een opgehaald antwoord
WAITS = (2, 5, 12)               # wachttijden (s) voor een nieuwe poging
NO_CONNECTION = ('No connection to Discogs. Check the internet connection and Sleeve’s network access; '
                 'you can also use your own reference photo.')


def cache_dir():
    d = os.environ.get('SLEEVE_NET_CACHE') or os.path.join(tempfile.gettempdir(), 'sleeve-net-cache')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def _cache_path(url):
    d = cache_dir()
    return os.path.join(d, hashlib.sha256(url.encode()).hexdigest()) if d else None


def _read_cache(url):
    p = _cache_path(url)
    try:
        if p and time.time() - os.path.getmtime(p) < TTL:
            with open(p, 'rb') as f:
                return f.read()
    except OSError:
        pass
    return None


def _write_cache(url, data):
    p = _cache_path(url)
    if not p or not data:
        return
    try:                                                   # eerst naast het doel schrijven: een ander onderdeel leest nooit een half bestand
        tmp = f'{p}.{os.getpid()}.tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, p)
    except OSError:
        pass


def _once(url):
    """Eén poging. Geeft (data, None) of (None, seconden wachten) bij 'probeer het zo weer';
    een andere fout komt als uitzondering."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=8) as r:
            return r.read(), None
    except urllib.error.HTTPError as error:
        if error.code == 429 or 500 <= error.code < 600:
            try:
                wait = float(error.headers.get('Retry-After') or 0)
            except (TypeError, ValueError):
                wait = 0
            return None, min(max(wait, 0), 30)
        raise RuntimeError(f'fetch failed ({error.code}): {url}') from error
    except Exception as error:
        if getattr(getattr(error, 'reason', error), 'errno', None) in (13, 51, 64, 65):
            raise RuntimeError(NO_CONNECTION) from error
        # lukt het niet met Python (bv. geen certificaten op deze Mac), dan met curl
        r = subprocess.run(['curl', '-sSL', '-A', UA, '--connect-timeout', '8', '--max-time', '20',
                            '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = r.stdout.rpartition(b'\n')
        code = code.decode('ascii', 'ignore').strip()
        if r.returncode == 0 and code.startswith('2'):
            return body, None
        if code == '429' or code.startswith('5') or r.returncode in (28, 52, 56):   # te druk, storing, of halverwege afgebroken
            return None, 0
        if r.returncode in (6, 7):                                                   # geen naam, geen verbinding
            raise RuntimeError(NO_CONNECTION) from error
        raise RuntimeError(f'fetch failed ({code or r.returncode}): {url}') from error


def fetch(url, sleep=time.sleep):
    """De inhoud van url (bytes): uit het geheugen als het er al is, anders ophalen."""
    data = _read_cache(url)
    if data is not None:
        return data
    for attempt in range(len(WAITS) + 1):
        data, wait = _once(url)
        if data is not None:
            _write_cache(url, data)
            return data
        if attempt == len(WAITS):
            break
        sleep(max(wait or 0, WAITS[attempt]))
        data = _read_cache(url)                            # een ander onderdeel kan het intussen opgehaald hebben
        if data is not None:
            return data
    raise RuntimeError('Discogs is not answering right now (too many requests or a fault on their side). Try again in a minute.')
