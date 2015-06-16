#!/usr/bin/env python

'''
Download all tax bills for a BBL or list of BBLs
'''

import sys
import requests
import bs4
import urlparse
import time
import os
import logging
import traceback

SEARCH_URL = 'http://webapps.nyc.gov:8084/CICS/fin1/find001i'
LIST_URL = 'http://nycprop.nyc.gov/nycproperty/nynav/jsp/stmtassesslst.jsp'

logging.basicConfig(format='%(asctime)-15s %(message)s')
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler(sys.stderr))
SESSION = requests.session()
DOCS_TO_DOWNLOAD = [
    u'Quarterly Statement of Account',  # Amounts paid, stabilized fees, other
                                        # charges, mailing address
    u'Quarterly Property Tax Bill',  # Amounts paid, stabilized fees, other
                                     # charges, mailing address, mortgagee
                                     # payer
    # u'SCRIE Statement of Account',  # SCRIE amounts, mailing address
    # skipping this because they're very, very slow
    u'Notice of Property Value',  # Estimated sq. footage, gross income,
                                  # expenses, RoI
    u'Tentative Assessment Roll',  # Real Estate billing name and address
                                   # (mortgagee payer)
]


class NYCServDownError(Exception):
    pass


def handle_double_dot(list_url, href):
    return urlparse.urljoin(list_url, href)


def handle_soalist(list_url, href):
    link_url = urlparse.urljoin(list_url, href)

    link_resp = SESSION.get(link_url, headers={'Referer': list_url})
    link_soup = bs4.BeautifulSoup(link_resp.text)

    statement_href = link_soup.select(
        'a[href^="../../StatementSearch"]')[0].get('href')
    return urlparse.urljoin(list_url, statement_href)


def find_extension(resp):
    """
    Extract whether a requests response is for HTML or PDF.
    """
    content_type = resp.headers['Content-Type']
    if 'html' in content_type:
        return 'html'
    elif 'pdf' in content_type:
        return 'pdf'


def save_file_from_stream(resp, filename):
    """
    Save a file from a streamed response
    """
    chunk_size = 1024
    with open(filename + '.' + find_extension(resp), 'wb') as fd:
        for chunk in resp.iter_content(chunk_size):
            fd.write(chunk)


def strain_soup(bbl, soup, target, get_statement_url):
    """
    Pull out all PDFs or HTML pages from a NYCServ soup, targetting certain
    links (`target`) and using `get_statement_url` to get the correct href for
    the actual statement.
    """
    for statement in soup.select(target):
        docname = statement.text.strip()
        if docname.split(' - ')[1] not in DOCS_TO_DOWNLOAD:
            LOGGER.info(u'Not worried about doctype "%s" for BBL %s, skipping',
                        docname, bbl)
            continue

        bbldir = os.path.join('data', bbl.replace('-', os.path.sep))
        filenames = ['.'.join(f.split('.')[:-1]) or f
                     for f in os.listdir(bbldir)]

        if docname in filenames:
            LOGGER.info(u'Already downloaded "%s" for BBL %s, skipping',
                        docname, bbl)
            continue

        statement_url = get_statement_url(LIST_URL, statement.get('href'))
        LOGGER.info(u'Downloading %s: %s', docname, statement_url)

        filename = os.path.join(bbldir, docname)
        resp = SESSION.get(statement_url, headers={'Referer': LIST_URL},
                           stream=True)

        save_file_from_stream(resp, filename)

        time.sleep(1)


def search(borough=None, houseNumber=None, street=None, block=None, lot=None):
    #if block and lot:
    #    data['FBLOCK'] = ('00000%s' % block)[-5:]
    #    data['FLOT'] = ('0000%s' % lot)[-4:]
    #    data['FEASE'] = ''
    #    data['FFUNC'] = 'C'
    if not borough:
       raise Exception("Need borough")
    if block and lot:
       block = str(block).zfill(5)
       lot = str(lot).zfill(4)
       bbl = '{}-{}-{}'.format(borough, block, lot)
       form = {
           'DFH_ENTER': 'PROCESSING',
           'FFUNC': 'A',
           'FMSG2': '02/03/06 10:30AM -       B4 5000-SEND-VARIABLES                                 ',
           'bblAcctKeyIn1': borough,
           'bblAcctKeyIn2': block, #'01280',
           'bblAcctKeyIn3': lot, #'0058',
           'bblAcctKeyIn4': ' ',
           'ownerName': '                                                                     ', #'991 CARROLL ST LLC   ',
           'ownerName1': '                                                                      ', #'991 CARROLL ST LLC                                                    ',
           'ownerName2': '                                                                      ',
           'ownerName3': '                                                                      ',
           'ownerName4': '                                                                      ',
           'ownercount': '', # '1',
           'q49_block_id': block, #'01280',
           'q49_boro': borough, #'3',
           'q49_lot': lot, #'0058',
           'q49_prp_ad_city': 'New york            ',
           'q49_prp_ad_street_no': '', # '991     ',
           'q49_prp_cd_addr_zip': '', #'11225',
           'q49_prp_cd_state': 'NY',
           'q49_prp_id_apt_num': '     ',
           'q49_prp_nm_street': '', #'CARROLL STREET                   ',
           'returnMsg': 'Note:'
       }
       #form = {
       #     'q49_boro': borough,
       #     'q49_block_id': block,
       #     'q49_lot': lot
       #}
    else:
        data = {
            'FBORO': borough,
        }
        if street and houseNumber:
            data['FSTNAME'] = street
            data['FHOUSENUM'] = houseNumber
        else:
            raise Exception("Need street and housenumber if not searching by BBL")
        resp = SESSION.post(SEARCH_URL, data=data)

        # Extract necessary form content based off of address
        soup = bs4.BeautifulSoup(resp.text)
        inputs = soup.form.findAll('input')
        form = dict([(i.get('name'), i.get('value')) for i in inputs])

        # Get property tax info page
        try:
            bbl = '{}-{}-{}'.format(form['q49_boro'],
                                    form['q49_block_id'],
                                    form['q49_lot'])
        except KeyError:
            raise NYCServDownError(resp.text)
            #LOGGER.error(u'No BBL found for %s', data)
            #return

    LOGGER.info(u'Pulling down %s', bbl)
    if not os.path.exists(os.path.join('data', bbl.replace('-', os.path.sep))):
        os.makedirs(os.path.join('data', bbl.replace('-', os.path.sep)))

    resp = SESSION.post(LIST_URL, data=form)

    # Maintenance page?
    if len(resp.text) == 7419:
        raise NYCServDownError(resp.text)

    soup = bs4.BeautifulSoup(resp.text)

    strain_soup(bbl, soup, 'a[href^="../../"]', handle_double_dot)
    strain_soup(bbl, soup, 'a[href^="soalist.jsp"]', handle_soalist) 

def main(*args):
    down_for_maintenance = True
    while down_for_maintenance:
        down_for_maintenance = False
        try:
            try:
                search(borough=args[0], block=int(args[1]), lot=int(args[2]))
            except ValueError:
                search(houseNumber=args[0], street=args[1], borough=args[2])
        except NYCServDownError as e:
            down_for_maintenance = True
        except requests.ConnectionError as e:
            if 'Connection aborted.' in str(e[0]):
                down_for_maintenance = True
            else:
                raise
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(traceback.format_exc())
            LOGGER.error(e)

        if down_for_maintenance:
            LOGGER.warn(u"NYCServ appears to be down, waiting: '%s'", e)
            time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        with open(sys.argv[1]) as infile:
            for line in infile:
                main(*line.strip().split('\t'))
    elif len(sys.argv) == 4:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        sys.stderr.write(u'''

    Should be called with one arg for tab-delimited file, three args for
    housenum/streetname/borough number.

''')
        sys.exit(1)
