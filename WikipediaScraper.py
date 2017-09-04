import re
import requests
import urllib2

from pattern.web import Element


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
            return urllib2.unquote(re.sub(r"<.*?>", "", cites[0].content))
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
            print content_str

    def search(self, token, hard_mode=False):
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
            token += "Wikipedia"

        url = self.get_first_url_from_google(token)
        self.extract_info_from_wiki_url(url)
        self.next()

    def search_hard(self, token):
        """
        same as search but just using hard mode
        """
        self.search(token, True)
