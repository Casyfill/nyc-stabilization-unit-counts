#!/bin/bash

source .env/bin/activate
python quarterly-property-tax-bills-pdf/scrape.py data/ >data/pdf-tax-bills.csv 2>data/pdf-tax-bills.log  &
python quarterly-statement-of-account-html/scrape.py data/ >data/html-statement-of-account.csv 2>data/html-statement-of-account.log  &
