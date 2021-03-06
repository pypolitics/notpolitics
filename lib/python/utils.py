# -*- coding: utf-8 -*-

# system libs
import requests, time, ast, locale, pprint, re, shutil, os, sys, json, copy, csv
from datetime import datetime, date
from fuzzywuzzy import fuzz
reload(sys) 
sys.setdefaultencoding('utf8')

companies_house_user = 'ZCCtuxpY7uvkDyxLUz37dCYFIgke9PKfhMlEGC-Q'

# Classes
class PrettyPrintUnicode(pprint.PrettyPrinter):
    """
    Subclassed Pretty Printer which handles unicode characters correctly
    """
    def format(self, object, context, maxlevels, level):
        if isinstance(object, unicode):
            return (object.encode('utf8'), True, False)
        return pprint.PrettyPrinter.format(self, object, context, maxlevels, level)

def get_request(url, user=None, headers={}, request_wait_time=300.00):
    # print url
    if user:
        request = requests.get(url, auth=(user, ''), headers=headers)
    else:
        request = requests.get(url, headers=headers)
    # print request
    if request.status_code == 200:
        return request

    # too many requests
    if request.status_code == 429:
        print '*'*100
        print "Too Many Requests, wait for %s seconds" % str(request_wait_time)
        print '*'*100
        time.sleep(request_wait_time)
        return get_request(url, user, headers)
    
    # temporarily unavailable
    elif request.status_code == 503:
        print '*'*100
        print "Temporarily Unavailable, wait for %s seconds" % str(request_wait_time)
        print '*'*100
        time.sleep(request_wait_time)
        return get_request(url, user, headers)

    else:
        return request

def get_all_mps(theyworkyou_apikey):
	"""
    Function to return a full list of current MPs
    """
	url = 'https://www.theyworkforyou.com/api/getMPs?key=%s&output=js' % (theyworkyou_apikey)
	request = get_request(url=url, user=None, headers={})
	# literal eval the json request into actual json
	literal = ast.literal_eval(request.content)

	return literal

def get_house_of_commons_member(constituency, outputs=None):

    search_criteria = 'House=Commons|IsEligible=true|constituency=%s' % (constituency)
    if not outputs:
        outputs = 'BasicDetails|Addresses|PreferredNames'
    url = 'http://data.parliament.uk/membersdataplatform/services/mnis/members/query/%s/%s' % (search_criteria, outputs)

    headers = {'Accept': 'application/json'}
    request = get_request(url=url, user=None, headers=headers)

    # replace null with None
    content = request.content.replace("null", "None")
    a = ast.literal_eval(content)

    members = a['Members']['Member']
    return members

def get_house_of_commons_member2(constituency):

    search_criteria = 'House=Commons|IsEligible=true|constituency=%s' % (constituency)
    outputs = 'GovernmentPosts|BiographyEntries|Committees'

    url = 'http://data.parliament.uk/membersdataplatform/services/mnis/members/query/%s/%s' % (search_criteria, outputs)

    headers = {'Accept': 'application/json'}
    request = get_request(url=url, user=None, headers=headers)

    # replace null with None
    content = request.content.replace("null", "None")
    a = ast.literal_eval(content)

    members = a['Members']['Member']
    return members

def get_mp_image(name, first_name, last_name, memid, output_path):
    """
    Function to return an image

    Due to parliament being dissolved at 12:01 on 03/05/2017, the members query returns nothing,
    simply because there are no members of parliament right now.

    For now, use an offline xml version.

    """

    # find the mp id from data.parliament
    url = 'http://data.parliament.uk/membersdataplatform/services/mnis/members/query/name*%s/' % (name)
    request = get_request(url=url, user=None, headers={'content-type' : 'application/json'})
    filepath = '%s/%s.jpg' % (output_path, memid)
    # print filepath

    if os.path.isfile(filepath):
        print 'Image Exists'
        return

    try:
        js = request.json()
        member_id = js['Members']['Member']['@Member_Id']

        # find the member photo
        url = 'http://data.parliament.uk/membersdataplatform/services/images/MemberPhoto/%s/Web Photobooks' % member_id
        response = requests.get(url, stream=True)

        with open(filepath, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
            print 'Downloaded : %s' % filepath
        del response
    except:
        pass

def string_to_datetime(date_string):
    """
    Returns a datetime class from a given string
    """
    return datetime.strptime(date_string, '%d %B %Y')

def padded_string(string, padding=100):
    """
    Return a padded string
    """
    return string.ljust(padding)

def regex_for_registered(raw_string):
    """
    Returns a date class formatted string
    """
    registered_regex = re.compile(r'\((.*?\))')
    registered_regex = re.compile(r"\bRegistered\b \d+ [A-Z][a-z]+ \d+")

    if registered_regex.findall(raw_string.encode('utf-8'), re.UNICODE):
        match = registered_regex.findall(raw_string)
        date = str(match[-1].split('Registered ')[-1])
        return string_to_datetime(date).strftime("%d/%m/%Y")
    else:
        return None

def regex_for_amount(raw_string):
    """
    Return integer amount
    """
    amount_regex = re.compile(r"£\d+")

    if amount_regex.search(raw_string.replace(',','').encode('utf-8')):

        return int(amount_regex.search(raw_string.replace(',', '').encode('utf-8')).group().split('£')[-1])
    else:
        return 0

def regex_for_percent(raw_string):
    """
    Return integer amount
    """
    amount_regex = re.compile(r"\d+%")

    if amount_regex.search(raw_string):

        return int(amount_regex.search(raw_string).group().split('%')[0])
    else:
        return 15

def regex_for_ownership(raw_string):
    """
    Return integer amount
    """
    amount_regex = re.compile(r"\d+-to-\d+")

    if amount_regex.search(raw_string):
        return amount_regex.search(raw_string).group().split('-to-')
    else:
        return None

def get_regex_pair_search(pair, raw_string):
    """
    Return a regex search class
    """
    return re.search(r'%s(.*?)%s' % (pair[0], pair[1]), raw_string)

def getlink(data, link):

    if data.has_key('links'):
        if data['links'].has_key(link):

            link_url = data['links'][link]
            url = 'https://api.companieshouse.gov.uk%s' % link_url
            link_request = get_request(url=url, user=companies_house_user, headers={})

            try:
                l = link_request.json()
                if not l.has_key('items'):
                    l['items'] = []
                return l
            except:
                return {'items' : []}
    return {'items' : []}

def contains_keywords(vals, keywords):
    """
    Check if a list of values contain our keywords
    """

    for search in keywords:
        for v in vals:
            if search.lower() in v.lower():
                # print 'MP FOUND : %s' % vals
                return True
    return False

def filter_by_name_string(data, display_as_name):
    """
    """
    # print display_as_name
    exclude_titles = ['mr', 'mrs', 'ms', 'miss', 'dr', 'sir', '']
    display_names = []
    for i in display_as_name.split(' '):
        if i not in exclude_titles:
            display_names.append(i)

    matched_people = []

    user = data
    # for user in data:
    if not user.has_key('title'):
        if user.has_key('name'):
            user['title'] = user['name']

    # get the title, split it
    title = user['title'].lower()
    title_splits = []
    for t in title.split(' '):
        title_splits.append(t.replace(',',''))

    # check if display names are in the title
    disp_match = True
    for disp in display_names:
        if disp.lower() in title_splits:
            pass
        else:
            disp_match = False

    if disp_match:
        # if the full display name is in the title, thats good enough
        matched_people.append(user)

    return matched_people

def read_sic_codes(sic):

    path = '../lib/data/sic_codes.csv'
    if os.path.isfile(path):
        pass
    else:
        path = '../data/sic_codes.csv'

    in_file = open(path, "rb")
    reader = csv.reader(in_file)
    next(reader, None)

    for row in reader:
        if sic == row[0]:
            return row[-1]
    return ''

def read_unincorporated(name):

    path = '../lib/data/unincorporated_associations.csv'
    if os.path.isfile(path):
        pass
    else:
        path = '../data/unincorporated_associations.csv'

    in_file = open(path, "rb")
    reader = csv.reader(in_file)
    next(reader, None)

    for row in reader:
        ratio  = fuzz.token_set_ratio(name.lower(), row[0].lower())
        # print name, row[0].lower(), ratio
        if ratio > 90:
            return row[0]
    return None

def cleanup_raw_string(raw, exclude_extra=[]):
    """Cleanup a raw string from the register of intrests, ready for querying with"""

    raw = raw.lower()
    raw_list = re.sub('[^0-9a-zA-Z]+', ' ', raw).split(' ')

    exclude = ['shareholder', 'director', 'of', 'services', 'service', 'recruitment', 'international', 'specialist','and', '(', ')', '%', 'registered', '', 'from', 'an', 'a', 'company', 'shareholding', 'shareholdings', 'business']
    for each in exclude_extra:
        exclude.append(each)

    months = [date(2000, m, 1).strftime('%b').lower() for m in range(1, 13)]
    months_short = [date(2000, m, 1).strftime('%B').lower() for m in range(1, 13)]
    for i in months:
        exclude.append(i)
    for i in months_short:
        exclude.append(i)

    found = []
    for r in raw_list:
        if r not in exclude:
            try:
                r = int(r)
            except:
                found.append(r)

    return ' '.join(found)

def read_json_file():
    """
    Read file from json_dump_location
    """
    json_dump_location = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'members')
    data = []
    for mp in os.listdir(json_dump_location):
        f = os.path.join(json_dump_location, mp)
        with open(f) as json_data:
            data.append(json.load(json_data))

    return data

def write_word_cloud(words, member_id, filepath, width=1600, height=1000, background_color='#cccccc', max_words=300):
    """
    Write out word cloud
    """
    # words to generate a clod from
    string = ''
    for w in words:
        spl = w.split(' ')
        for i in spl:
            if i != '':
                i = i.replace('-', ' ').replace('/', ' ')
                string += '%s ' % i.lower()

    stopwords = ['other', 'member', 'trading', 'companies', 'uk', 'and', 'none', 'from', 'of', 'for', 'in', 'on', 'true', 'false', 'england', 'scotland', 'wales', 'northern', 'ireland', 'officers', 'active', 'company', 'street', 'director', 'london', 'limited', 'corporate', 'secretary', 'dissolved', 'officer', 'united', 'kingdom', 'british', 'appointments', 'appointment', 'mr', 'mrs', 'ms', 'miss', 'the', 'ltd', 'limited', 'plc', 'llp']

    wordcloud = WordCloud(background_color=background_color, mode="RGBA", width=width, height=height, max_words=max_words, stopwords=stopwords, colormap="Set1").generate(string)
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")

    print 'Writing : %s' % filepath
    plt.savefig(filepath, transparent=True, bbox_inches='tight', pad_inches=0, dpi=300)

def read_expenses(expenses_data):
    """
    read expenses csv file, organise into ready made plot categories
    """

    expenses_dictionary = {}
    office = ['Office spend', 'Staffing spend', 'Startup spend', 'Windup spend']
    other = ['Accommodation spend', 'Travel/subs spend', 'Other spend']
    total = []

    keys = office + other + total

    for year in expenses_data.keys():
        expenses_dictionary[year] = []
        with open(expenses_data[year], 'rb') as f:

            # replace null
            reader = csv.reader(x.replace('\0', '').replace('\xef\xbb\xbf', '').replace(' CC', '').replace(' BC', '') for x in f)
            headers = reader.next()

            for row in reader:
                if row != []:
                    data = {'office' : {'items' : []}, 'other' : {'items' : []}}

                    data = {}
                    data['category_amount'] = 0
                    data['category_description'] = '%s' % year.replace('-', ' - ')
                    data['isCurrency'] = True
                    data['items'] = []
                    data['name'] = row[headers.index('MP name')].replace(u'\xa3', '').replace(',','')
                    data['constituency'] = row[headers.index('Constituency')].replace(' CC', '').replace(' BC', '')

                    for head in headers:
                        if head in keys:
                            i = head.decode('utf-8')
                            cell = row[headers.index(head)]
                            cell_amount = cell.replace(u'\xa3', '').replace(',','')
                            try:
                                amount = int(float(cell_amount))
                            except:
                                amount = amount

                            item = {}
                            item['amount'] = amount
                            item['pretty'] = head
                            item['category_id'] = 13

                            data['items'].append(item)

                    expenses_dictionary[year].append(data)
            f.close()

    return expenses_dictionary

def match_expenses(mp, year, expenses_dictionary):
    """
    Match a year and an mp to its expenses record
    """
    for ex in expenses_dictionary[year]:
        if mp['name'] == ex['name']:
            return [ex]
        elif mp['constituency'] == ex['constituency']:
            return [ex]

    print 'Unmatched : ', mp['name']
    return {'items' : [], 'category_amount' : 0, 'category_description' : year, 'category_id' : 12, 'isCurrency' : True, 'name' : mp['name']}
