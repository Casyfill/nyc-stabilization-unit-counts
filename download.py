#!/usr/bin/env python

import sys
import requests
import bs4
import urlparse
import time
import os
import re

FIND_BBL_URL = 'http://webapps.nyc.gov:8084/CICS/fin1/find001i'

def strainSoup(search_value):
  '''
  iterate over html based on an href value
  '''
  if search_value == 'first':
      target = 'a[href^="../../"]'
  elif search_value == 'second':
      target = 'a[href^="soalist.jsp"]'

  for statement in soup.select(target):
    link_text = statement.text.strip()
    href = statement.get('href')

    if search_value == 'first':
      statement_url = urlparse.urljoin(list_url, href)
      sys.stderr.write(u'{0}: {1}\n'.format(link_text, statement_url))

    elif search_value == 'second':
      link_url = urlparse.urljoin(list_url, href)
      sys.stderr.write(u'{0}: {1}\n'.format(link_text, link_url))

      link_resp = session.get(link_url, headers={'Referer': list_url})
      link_soup = bs4.BeautifulSoup(link_resp.text)

      statement_href = link_soup.select('a[href^="../../StatementSearch"]')[0].get('href')
      statement_url = urlparse.urljoin(list_url, statement_href)

    test = session.get(statement_url, stream=True)
    content_type = test.headers['Content-Type']

    if re.search(r'html', content_type, re.M|re.I):
      filename = os.path.join('data', bbl, link_text + '.html')
      if os.path.exists(filename):
        continue
    elif re.search(r'pdf', content_type, re.M|re.I):
      filename = os.path.join('data', bbl, link_text + '.pdf')
      if os.path.exists(filename):
        continue

    resp = session.get(statement_url, headers={'Referer': list_url}, stream=True)

    chunk_size = 1024
    with open(filename, 'wb') as fd:
      for chunk in resp.iter_content(chunk_size):
        fd.write(chunk)

    time.sleep(1)

def main(houseNumber, street, borough):
  global soup
  global list_url
  global bbl
  global session
  sys.stderr.write(u'{0} {1}, {2}\n'.format(houseNumber, street, borough))
  session = requests.session()
  resp = session.post(FIND_BBL_URL, data={
    'FBORO':borough,
    'FSTNAME':street,
    'FHOUSENUM':houseNumber})

  # Extract necessary form content based off of address
  soup = bs4.BeautifulSoup(resp.text)
  list_url = soup.form.get('action').lower()
  inputs = soup.form.findAll('input')
  form = dict([(input.get('name'), input.get('value')) for input in inputs])

  # Get property tax info page
  bbl = '{}-{}-{}'.format(form['q49_boro'],
                          form['q49_block_id'],
                          form['q49_lot'])
  if not os.path.exists(os.path.join('data', bbl)):
    os.makedirs(os.path.join('data', bbl))

  resp = session.post(list_url, data=form)
  soup = bs4.BeautifulSoup(resp.text)

  strainSoup('first')
  strainSoup('second')

if __name__ == '__main__':
  if len(sys.argv) == 2:
    with open(sys.argv[1]) as infile:
      for line in infile:
        args = line.strip().split('\t')
        main(args[0], args[1], args[2])
  elif len(sys.argv) == 4:
    main(sys.argv[1], sys.argv[2], sys.argv[3])
  else:
    sys.stderr.write(u'''

    Should be called with one arg for tab-delimited file, three args for
    housenum/streetname/borough number.

''')
    sys.exit(1)
