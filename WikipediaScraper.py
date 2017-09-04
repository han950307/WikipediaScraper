import re
import requests
import urllib2
import os
import shlex
import struct
import platform
import subprocess
import warnings

from bs4 import BeautifulSoup
from pattern.web import Element


warnings.filterwarnings("ignore", category=UserWarning, module='bs4')


class TerminalSizeGetter(object):
    """
    Helper class that gets terminal size. Source:
    https://gist.githubusercontent.com/jtriley/1108174/raw/6ec4c846427120aa342912956c7f717b586f1ddb/terminalsize.py
    """
    def get_terminal_size(self):
        """ getTerminalSize()
         - get width and height of console
         - works on linux,os x,windows,cygwin(windows)
         originally retrieved from:
         http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python
        """
        current_os = platform.system()
        tuple_xy = None
        if current_os == 'Windows':
            tuple_xy = self._get_terminal_size_windows()
            if tuple_xy is None:
                tuple_xy = self._get_terminal_size_tput()
                # needed for window's python in cygwin's xterm!
        if current_os in ['Linux', 'Darwin'] or current_os.startswith('CYGWIN'):
            tuple_xy = self._get_terminal_size_linux()
        if tuple_xy is None:
            print "default"
            tuple_xy = (80, 25)      # default value
        return tuple_xy

    def _get_terminal_size_windows(self):
        try:
            from ctypes import windll, create_string_buffer
            # stdin handle is -10
            # stdout handle is -11
            # stderr handle is -12
            h = windll.kernel32.GetStdHandle(-12)
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
            if res:
                (bufx, bufy, curx, cury, wattr,
                 left, top, right, bottom,
                 maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
                sizex = right - left + 1
                sizey = bottom - top + 1
                return sizex, sizey
        except:
            pass

    def _get_terminal_size_tput(self):
        # get terminal width
        # src: http://stackoverflow.com/questions/263890/how-do-i-find-the-width-height-of-a-terminal-window
        try:
            cols = int(subprocess.check_call(shlex.split('tput cols')))
            rows = int(subprocess.check_call(shlex.split('tput lines')))
            return (cols, rows)
        except:
            pass

    def _get_terminal_size_linux(self):
        def ioctl_GWINSZ(fd):
            try:
                import fcntl
                import termios
                cr = struct.unpack('hh',
                                   fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
                return cr
            except:
                pass
        cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = ioctl_GWINSZ(fd)
                os.close(fd)
            except:
                pass
        if not cr:
            try:
                cr = (os.environ['LINES'], os.environ['COLUMNS'])
            except:
                return None
        return int(cr[1]), int(cr[0])


class Scraper(object):
    """
    Parent scraper with all the necessary functions
    """
    def scrape_page(self, url):
        """
        scrapes the url and returns the html
        """
        r = requests.get(url)
        return r.content

    def convert_html_to_element(self, page_html):
        """
        converts html to Element object
        """
        return Element(page_html)

    def format_url(self, url):
        """
        formats url so that it's quoted properly.
        """
        if not isinstance(url, unicode):
            url = unicode(url, "utf-8")

        # pop the header for now
        header = re.search(r"(http\:\/\/|https\:\/\/)", url).group(0)
        url = re.sub(header, "", url)

        # format url
        formatted_url = urllib2.quote(url.encode("utf-8"))

        return header + formatted_url


class WikipediaScraper(Scraper):
    """
    Scraper class for scraping basic information from wikipedia
    """
    GOOGLE_SEARCH_URL = "https://www.google.com/search?q={}"
    CHAR_PER_LINE = 65

    contents = []
    cur_ind = 0

    def get_first_url_from_google(self, token):
        """
        Returns the url from the first google search result using the token.
        """
        # replace spaces with +
        query = urllib2.quote(token)

        # get the html
        web = self.scrape_page(self.GOOGLE_SEARCH_URL.format(query))

        # make it into an element
        el = self.convert_html_to_element(web)
        # Get the first url
        cites = el("cite")
        if cites:
            ind = 0
            unquoted = urllib2.unquote(re.sub(r"<.*?>", "", cites[0].content))
            beautified = BeautifulSoup(unquoted, 'html.parser').contents[0]

            # Sometimes it chooses "Category:token" so want to avoid that.
            while re.search(r"category\:" + token.split()[0], beautified, re.I):
                ind += 1
                if ind >= len(cites):
                    break
                unquoted = urllib2.unquote(re.sub(r"<.*?>", "", cites[ind].content))
                beautified = BeautifulSoup(unquoted, 'html.parser').contents[0]
            return beautified
        else:
            print "No URLs found on Google Search"
            return ""

    def extract_info_from_wiki_url(self, url):
        """
        returns the summary portion from the wikipedia url
        """
        url = self.format_url(url)
        web = self.scrape_page(url)
        el = self.convert_html_to_element(web)
        contents = el(".mw-parser-output > p")
        if contents:
            self.contents = contents
        else:
            print "No wikipedia summary found"
            return ""

    def print_text(self, text):
        """
        prints the text so that it doesn't break char per line limit
        or breaks words
        """
        tsg = TerminalSizeGetter()
        sizex, sizey = tsg.get_terminal_size()
        if not sizex:
            sizex = self.CHAR_PER_LINE

        words = text.split()
        cur_ind = 0
        buf = ""

        # keep adding to buffer while ind is less than length
        while cur_ind < len(words):
            # if buf reached the char per line limit, then flush buffer
            if len(buf) + len(words[cur_ind]) + 1 > sizex:
                print buf.strip()
                buf = ""

            buf += words[cur_ind] + " "
            cur_ind += 1

        print buf.strip()

    def next(self):
        """
        prints the next paragraph from the wikipedia.
        """
        content_str = ""

        # until we find an acutal content, keep going.
        while not content_str:
            if self.cur_ind < len(self.contents):
                content_str = re.sub(r"<.*?>", "", self.contents[self.cur_ind].content)
                content_str = content_str.strip()
                self.cur_ind += 1
            else:
                print "Reached end of document"
                return

        if content_str:
            self.print_text(content_str)

    def search(self, token, hard_mode=True):
        """
        Scrapes simple wikipedia summary. If hard_mode=True, searches
        normal wikipedia summary.
        """
        self.cur_ind = 0
        self.contents = []

        # get rid of trailing whitespaces and other characters
        token = token.strip()

        # decide whether to use simple wikipedia or normal
        if not hard_mode:
            token += " Simple English Wikipedia"
        else:
            token += " Wikipedia"

        url = self.get_first_url_from_google(token)
        self.extract_info_from_wiki_url(url)
        self.next()

    def search_easy(self, token):
        """
        same as search but just using hard mode
        """
        self.search(token, False)
