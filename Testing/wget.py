import BeautifulSoup
from operator import itemgetter
from xml.etree import ElementTree
import datetime
import urllib2
import xlwt
import copy
import sys
import csv
import os
import logging
import argparse

logging.basicConfig(filename = 'swob.log', format='[%(asctime)s] [%(levelname)s] line=%(lineno)s module=%(module)s function=%(funcName)s [%(message)s]',
    datefmt = '%a, %d %b %Y %H:%M:$S', level = logging.DEBUG)
if not os.path.isfile("wget.log"):
    open("wget.log","w")
    close("wget.log")

def get_stations_list(urlroot, strdate):
    """
    Returns a list of the all stations for which swob-ml observations are available
    :param urlroot: (str) the root url to base searches from
    :param strdate: (str) the date string in YYYYMMDD format
    :returns: (list) of str with 3 letter station designations
    """
    all_stations_list = []
    all_stations_html = get_html_string(urlroot+strdate+"/")
    all_stations_soup = BeautifulSoup.BeautifulSoup(all_stations_html)

    for tag in all_stations_soup.findAll('a', href=True):
        #length is 5: eg. "CVSL/", we remove the "/" to get station name
        if tag['href'].__len__() == 5:
            tag['href'] = tag['href'].replace("/","")
            tag['href'] = tag['href'][1:].encode('ascii','ignore')
            all_stations_list.append(tag['href'])

    return all_stations_list

date = datetime.datetime.utcnow()
strdate = date.strftime("%Y%m%d")

urlroot = "http://dd.weather.gc.ca/observations/swob-ml/" + strdate



