import csv
import sys
import os
import errno
import urllib
import urllib2
import re
import time
from lxml import etree

class Sanborn(object):
    def __init__(self):
        self.cookie_header = 'CPL=opdsnfq8suo2dctarcsr9g51k1; p=949812604336; s=G; e=0; UrlText=; Client_ID=10234; ezproxy=D33vcTMPrJ7a1h5; CCSI=11073'

    def _get_with_cookie(self, url, base_url='http://sanborn.umi.com.covers.chipublib.org/il/'):
        req = urllib2.Request('%s%s' % (base_url, url))
        req.add_header('Cookie', self.cookie_header)
        res = urllib2.urlopen(req)
        return res

    def get_dates(self, loc_id):
        html_fl = self._get_with_cookie('%s/dates-step3b.htm' % loc_id)

        parser = etree.HTMLParser()
        tree = etree.parse(html_fl, parser)

        date_options = tree.xpath('/html/body/table/tr[2]/td/form/select/option[@value]')

        res = {}
        for option in date_options:
            res[option.get('value')] = option.text

        return res

    def get_sheets(self, loc_id, date_code):
        sheet_page = 1

        sheets = []
        while True:
            has_more_pages = False
            print "Fetching locid %s, date %s, page %s." % (loc_id, date_code, sheet_page)
            html_fl = self._get_with_cookie('%s/%s-sheets-%da.htm' % (loc_id, date_code, sheet_page))

            for line in html_fl:
                #print line

                matches = re.match("<a href=\"javascript:MM_openBrWindow\('\.\.\/\.\.\/image\/view\?state=il&amp;reelid=(.*?)&amp;lcid=(\d*)&amp;imagename=(\d*)&amp;mapname=(.*?)',", line)
                if matches:
                    full_sheet_name = matches.group(4).replace('%20', ' ')
                    (date_name, sheet_name) = full_sheet_name.split(', Sheet ')
                    sheets.append({
                        "reel_id": matches.group(1),
                        "loc_id": matches.group(2),
                        "image_id": matches.group(3),
                        "date_name": date_name,
                        "sheet_name": sheet_name
                    })
                    print "Found image %s: %s" % (matches.group(3), matches.group(4).replace('%20', ' '))

                if line.startswith("   document.write('name=\"next\" ');"):
                    # We'll need to fetch the next page
                    print "Has at least one more page."
                    has_more_pages = True
                    sheet_page += 1

            if not has_more_pages:
                break

        return sheets

    def get_image(self, sheet_dict, width=500):
        encoded_qwargs = urllib.urlencode({
            "state": "il",
            "reelid": sheet['reel_id'],
            "lcid": sheet['loc_id'],
            "imagename": sheet['image_id'],
            "width": width
        })
        return self._get_with_cookie('?%s' % encoded_qwargs, base_url='http://sanborn.umi.com.covers.chipublib.org/sanborn/image/fetchimage')

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

if __name__ == '__main__':
    s = Sanborn()

    locids = csv.reader(open('location_ids.csv', 'r'))

    for line in locids:
        lcid = line[0]
        lcname = line[1]
        date_codes = s.get_dates(lcid)

        for (date_code, date_name) in date_codes.iteritems():
            sheets = s.get_sheets(lcid, date_code)

            root_dir = '%s (%s)/%s/' % (lcid, lcname.strip(), date_name.strip())
            mkdir_p(root_dir)
            for sheet in sheets:
                image_path = os.path.join(root_dir, 'r%sl%si%ss%s.gif' % (sheet['reel_id'], sheet['loc_id'], sheet['image_id'], sheet['sheet_name']))

                if os.path.exists(image_path):
                    print "Skipping %s as it already exists." % image_path
                    continue

                print "Downloading to %s" % image_path

                retries = 0
                retry_time = 1.0
                while retries < 3:
                    try:
                        f = open(image_path, 'w')
                        f.write(s.get_image(sheet, width=7000).read())
                        f.close()
                    except urllib2.URLError, e:
                        print "Trying again after %0.1fs because: %s" % (retry_time, e)
                        time.sleep(retry_time)
                        retries += 1
                        retry_time *= 2.0
