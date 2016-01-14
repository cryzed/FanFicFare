import re
import urlparse
import urllib2
import datetime

from .. import exceptions
from base_adapter import BaseSiteAdapter
from ..htmlcleanup import stripHTML

SITE_DOMAIN = 'quotev.com'
STORY_URL_TEMPLATE = 'http://www.quotev.com/story/%s'


def getClass():
    return QuotevComAdapter


def get_url_path_segments(url):
    return tuple(filter(None, url.split('/')[3:]))


class QuotevComAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)

        story_id = get_url_path_segments(url)[1]
        self._setURL(STORY_URL_TEMPLATE % story_id)
        self.story.setMetadata('storyId', story_id)
        self.story.setMetadata('siteabbrev', SITE_DOMAIN)

    @staticmethod
    def getSiteDomain():
        return SITE_DOMAIN

    @classmethod
    def getSiteExampleURLs(cls):
        return STORY_URL_TEMPLATE % '1234'

    def getSiteURLPattern(self):
        pattern = re.escape(STORY_URL_TEMPLATE.rsplit('%', 1)[0]) + r'(.+?)($|&|/)'
        pattern = pattern.replace(r'http\:', r'https?\:')
        pattern = pattern.replace(r'https?\:\/\/www\.', r'https?\:\/\/(www\.)?')
        return pattern

    def use_pagecache(self):
        return True

    def extractChapterUrlsAndMetadata(self):
        try:
            data = self._fetchUrl(self.url)
        except urllib2.HTTPError:
            raise exceptions.FailedToDownload(self.url)

        soup = self.make_soup(data)

        element = soup.find('div', {'class': 'result'})
        if not element:
            raise exceptions.StoryDoesNotExist(self.url)

        self.story.setMetadata('title', element.find('h1').get_text())

        # quotev html is all about formatting without any content tagging
        authdiv = soup.find('div', {'style':"text-align:left;"})
        if authdiv:
            #print("div:%s"%authdiv.find_all('a'))
            for a in authdiv.find_all('a'):
                self.story.addToList('author', a.get_text())
                self.story.addToList('authorId', a['href'].split('/')[-1])
                self.story.addToList('authorUrl', urlparse.urljoin(self.url, a['href']))
        else:
            self.story.setMetadata('author','Anonymous')
            self.story.setMetadata('authorUrl','http://www.quotev.com')
            self.story.setMetadata('authorId','0')

        self.setDescription(self.url, soup.find('div', id='qdesct'))
        self.setCoverImage(self.url, urlparse.urljoin(self.url, soup.find('img', {'class': 'logo'})['src']))

        for a in soup.find_all('a', {'href': re.compile(SITE_DOMAIN+'/stories/c/')}):
            self.story.addToList('category', a.get_text())

        for a in soup.find_all('a', {'href': re.compile(SITE_DOMAIN+'/search/')}):
            self.story.addToList('searchtags', a.get_text())

        elements = soup.find_all('span', {'class': 'q_time'})
        self.story.setMetadata('datePublished', datetime.datetime.fromtimestamp(float(elements[0]['ts'])))
        if len(elements) > 1:
            self.story.setMetadata('dateUpdated', datetime.datetime.fromtimestamp(float(elements[1]['ts'])))

        metadiv = elements[0].parent
        
        if 'completed' in stripHTML(metadiv):
            self.story.setMetadata('status', 'Completed')
        else:
            self.story.setMetadata('status', 'In-Progress')        

        data = filter(None, (x.strip() for x in stripHTML(metadiv).split(u'\xb7')))

        for datum in data:
            parts = datum.split()
            if len(parts) < 2 or parts[1] not in self.getConfig('extra_valid_entries'):
                continue
            # Not a valid metadatum
            # if not len(parts) == 2:
            #     continue

            key, value = parts[1], parts[0]
            self.story.setMetadata(key, value.replace(',', '').replace('.', ''))

        favspans = soup.find('a',{'id':'fav_btn'}).find_all('span')
        if len(favspans) > 1:
            self.story.setMetadata('favorites', stripHTML(favspans[1]).replace(',', ''))
            
        commentspans = soup.find('a',{'id':'comment_btn'}).find_all('span')
        #print("commentspans:%s"%commentspans)
        if len(commentspans) > 0:
            self.story.setMetadata('comments', stripHTML(commentspans[0]).replace(',', ''))

        for a in soup.find('div', id='rselect')('a'):
            self.chapterUrls.append((a.get_text(), urlparse.urljoin(self.url, a['href'])))

        self.story.setMetadata('numChapters', len(self.chapterUrls))
        
    def getChapterText(self, url):
        data = self._fetchUrl(url)
        soup = self.make_soup(data)

        element = soup.find('div', id='rescontent')
        for a in element('a'):
            a.unwrap()

        return self.utf8FromSoup(url, element)
