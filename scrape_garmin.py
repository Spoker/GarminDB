#!/usr/bin/env python

#
# copyright Tom Goetz
#

import os, sys, getopt, re, logging, datetime, time, tempfile, zipfile, json, dateutil.parser

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

import GarminDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Scrape():

    garmin_connect_base_url = "https://connect.garmin.com"
    garmin_connect_login_url = garmin_connect_base_url + "/en-US/signin"
    garmin_connect_modern_url = garmin_connect_base_url + "/modern"
    garmin_connect_daily_url = garmin_connect_modern_url + "/dailySummary/timeline"
    garmin_connect_daily_user_base_url = garmin_connect_modern_url + "/daily-summary"
    garmin_connect_weight_base_url = garmin_connect_modern_url + "/weight"
    garmin_connect_activities_url = garmin_connect_modern_url + "/activities"

    # timeout is seconds
    initial_page_load_timeout = 30
    page_reload_timeout = 15

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info("Creating profile: temp_dir= " + self.temp_dir)
        fp = webdriver.FirefoxProfile()
        fp.set_preference("browser.download.folderList", 2)
        fp.set_preference("browser.helperApps.alwaysAsk.force", False)
        fp.set_preference("browser.download.manager.showWhenStarting", False)
        fp.set_preference("browser.download.dir", self.temp_dir)
        fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
        fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
        fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-zip-compressed")
        geckodriver = os.getcwd() + "/bin/geckodriver"
        logger.debug("Creating driver")
        self.browser = webdriver.Firefox(firefox_profile=fp, executable_path=geckodriver)

    def __del__(self):
        self.browser.close()

    def load_page(self, url):
        logger.info("load_page: " + url)
        self.browser.switch_to.default_content()
        self.browser.get(url)

    def switch_frame_by_id(self, parent, id):
        logger.info("switch_frame_by_id: " + id)
        frame = parent.find_element_by_id(id)
        self.browser.switch_to.frame(frame)

    def fill_field_by_id(self, parent, id, value):
        logger.debug("fill_field_by_id: %s = %s" % (id, value))
        field = parent.find_element_by_id(id)
        field.click()
        field.clear()
        field.send_keys(value)

    def click_by_id(self, parent, id):
        logger.info("click_by_id: " + id)
        submit_button = parent.find_element_by_id(id)
        submit_button.click()

    def click_by_xpath(self, parent, xpath):
        logger.info("click_by_xpath: " + xpath)
        submit_button = parent.find_element_by_xpath(xpath)
        submit_button.click()

    def dump_elements(self, elements):
        for element in elements:
            logger.info("<%s class='%s'>%s</%s>" % (element.tag_name, element.get_attribute("class"),  element.text, element.tag_name))

    def dump_children(self, element):
        logger.info("dump_children: %s" % (repr(element)))
        self.dump_elements(element.find_elements_by_xpath(".//*"))

    def dump_children_by_tag(self, element, tag):
        logger.info("dump_children_by_tag: %s -> %s" % (repr(element), tag))
        self.dump_elements(element.find_elements_by_tag_name(tag))

    def get_children_by_tag(self, element, tag):
        logger.info("dump_children_by_tag: %s -> %s" % (repr(element), tag))
        return element.find_elements_by_tag_name(tag)

    def wait_for_id(self, driver, time_s, id):
        logger.info("Waiting for: " + id)
        return WebDriverWait(driver, time_s).until(EC.presence_of_element_located((By.ID, id)))

    def wait_for_xpath(self, driver, time_s, xpath):
        logger.info("Waiting for: " + xpath)
        return WebDriverWait(driver, time_s).until(EC.presence_of_element_located((By.XPATH, xpath)))

    def wait_for_pagecontainer(self, driver, time_s):
        logger.debug("wait_for_pagecontainer: ")
        time.sleep(1)
        return self.wait_for_xpath(driver, time_s, "//div[@id='pageContainer']")

    def get_profile_name(self, driver):
        logger.debug("get_profile_name: ")
        profile_name = driver.execute_script('return App.displayName')
        logger.info("Profile name: " + profile_name)
        return profile_name

    def login(self, username, password):
        logger.debug("login: %s %s" % (username, password))
        self.load_page(self.garmin_connect_login_url)
        self.wait_for_xpath(self.browser, self.initial_page_load_timeout, "//div[@class='page-container']")
        self.switch_frame_by_id(self.browser, "gauth-widget-frame-gauth-widget")
        self.fill_field_by_id(self.browser, "username", username)
        self.fill_field_by_id(self.browser, "password", password)
        self.click_by_id(self.browser, "login-btn-signin")

    def save_monitoring(self, parent):
        logger.debug("Finding dropdown")
        dropdown = parent.find_element_by_xpath("//*[@class='dropdown page-dropdown']")
        logger.debug("clicking button")
        dropdown.click()
        logger.debug("Finding button")
        button = dropdown.find_element_by_class_name("btn-export-original")
        logger.debug("clicking button")
        button.click()
        time.sleep(5)

    def browse_daily_page(self, profile_name, date):
        logger.info("browse_daily_page: %s %s" % (profile_name, repr(date)))
        daily_url = self.garmin_connect_daily_user_base_url + ("/%s/%s/timeline" % (profile_name, date.strftime("%Y-%m-%d")))
        self.load_page(daily_url)
        page_container = self.wait_for_pagecontainer(self.browser, self.initial_page_load_timeout)
        self.save_monitoring(page_container)

    def get_monitoring(self, date, days):
        logger.info("get_monitoring: %s : %d" % (str(date), days))
        self.load_page(self.garmin_connect_daily_url)
        page_container = self.wait_for_pagecontainer(self.browser, self.initial_page_load_timeout)
        profile_name = self.get_profile_name(self.browser)
        for day in xrange(0, days):
            day_date = date + datetime.timedelta(day)
            try:
                self.browse_daily_page(profile_name, day_date)
            except TimeoutException:
                logger.error("get_monitoring: timed out on day %d of %d" % (day, days))

    def unzip_monitoring(self, outdir):
        logger.info("unzip_monitoring: " + outdir)
        for filename in os.listdir(self.temp_dir):
            monitoring_files_zip = zipfile.ZipFile(self.temp_dir + "/" + filename, 'r')
            monitoring_files_zip.extractall(outdir)
            monitoring_files_zip.close()

    def get_weight_year(self, page_container):
        chart_div = page_container.find_element_by_xpath("//div[@data-highcharts-chart]")
        chart_number = chart_div.get_attribute('data-highcharts-chart')
        data = self.browser.execute_script('return Highcharts.charts[' + chart_number + '].series[0].options.data')
        points = []
        for entry in data:
            x = None
            if isinstance(entry, list):
                x = entry[0]
                y = entry[1]
            elif isinstance(entry, dict):
                x = entry['x']
                y = entry['y']
            else:
                logger.error("Unknown type: " + repr(entry))
            point = {'timestamp' : datetime.datetime.fromtimestamp(x / 1000), 'weight' : y}
            points.append(point)
        # first and last points are the ends of the graph and not valid, remove them
        del points[0]
        del points[-1]
        return points

    def get_weight(self):
        logger.info("get_weight")
        points = []
        self.load_page(self.garmin_connect_weight_base_url)
        page_container = self.wait_for_pagecontainer(self.browser, self.initial_page_load_timeout)
        self.click_by_id(page_container, "lastYearLinkId")
        while True:
            time.sleep(1)
            page_container = self.wait_for_pagecontainer(self.browser, self.page_reload_timeout)
            new_points = self.get_weight_year(page_container)
            points += new_points
            try:
                self.click_by_xpath(page_container, "//button[@class='icon-arrow-left']")
            except:
                break
        return points


def convert_to_json(object):
    return object.__str__()


def usage(program):
    print '%s -d [<date> -n <days> | -l <path to dbs>] -u <username> -p <password> [-m <outdir> | -w ]' % program
    print '  -d <date ex: 01/21/2018> -n <days> fetch n days of monitoring data starting at date'
    print '  -l check the garmin DB and find out what the most recent date is and fetch monitoring data from that date on'
    print '  -m <outdir> fetches the daily monitoring FIT files for each day specified, unzips them, and puts them in outdit'
    print '  -w <outdit> fetches the daily weight data for each day specified and puts them in the DB'
    sys.exit()

def main(argv):
    date = None
    days = None
    latest = False
    db_params_dict = {}
    username = None
    password = None
    monitoring = None
    weight = None
    debug = False

    try:
        opts, args = getopt.getopt(argv,"d:n:lm:p:s:tu:w:",
            ["debug", "date=", "days=", "username=", "password=", "latest", "monitoring=", "mysql=", "sqlite=", "weight="])
    except getopt.GetoptError:
        usage(sys.argv[0])

    for opt, arg in opts:
        if opt == '-h':
            usage(sys.argv[0])
        elif opt in ("-t", "--debug"):
            debug = True
        elif opt in ("-d", "--date"):
            logger.debug("Date: " + arg)
            date = dateutil.parser.parse(arg).date()
        elif opt in ("-n", "--days"):
            logger.debug("Days: " + arg)
            days = int(arg)
        elif opt in ("-l", "--latest"):
            logger.debug("Latest" )
            latest = True
        elif opt in ("-u", "--username"):
            logger.debug("Username: " + arg)
            username = arg
        elif opt in ("-p", "--password"):
            logger.debug("Password: " + arg)
            password = arg
        elif opt in ("-m", "--monitoring"):
            logger.debug("Monitoring: " + arg)
            monitoring = arg
        elif opt in ("-w", "--weight"):
            logger.debug("Weight")
            weight = arg
        elif opt in ("-s", "--sqlite"):
            logging.debug("Sqlite DB path: %s" % arg)
            db_params_dict['db_type'] = 'sqlite'
            db_params_dict['db_path'] = arg
        elif opt in ("--mysql"):
            logging.debug("Mysql DB string: %s" % arg)
            db_args = arg.split(',')
            db_params_dict['db_type'] = 'mysql'
            db_params_dict['db_username'] = db_args[0]
            db_params_dict['db_password'] = db_args[1]
            db_params_dict['db_host'] = db_args[2]

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if ((not date or not days) and not latest) and monitoring:
        print "Missing arguments: specify date and days or latest when scraping monitoring data"
        usage(sys.argv[0])
    if not username or not password:
        print "Missing arguments: need username and password"
        usage(sys.argv[0])
    if len(db_params_dict) == 0 and monitoring and latest:
        print "Missing arguments: must specify <db params> with --sqlite or --mysql"
        usage(sys.argv[0])

    if latest and monitoring:
        mondb = GarminDB.MonitoringDB(db_params_dict)
        last_ts = GarminDB.Monitoring.latest_time(mondb)
        if last_ts is None:
            days = 365
            date = datetime.datetime.now().date() - datetime.timedelta(days)
            logger.info("Automatic date not found, using: " + str(date))
        else:
            # start from the day after the last day in the DB
            logger.info("Automatically downloading monitoring data from: " + str(last_ts))
            date = last_ts.date() + datetime.timedelta(1)
            days = (datetime.datetime.now().date() - date).days

    if monitoring and days > 0:
        logger.info("Date range to update: %s (%d)" % (str(date), days))
        scrape = Scrape()
        scrape.login(username, password)
        scrape.get_monitoring(date, days)
        scrape.unzip_monitoring(monitoring)
        logger.info("Saved monitoring files for %s (%d) to %s for processing" % (str(date), days, monitoring))

    if weight:
        scrape = Scrape()
        scrape.login(username, password)
        points = scrape.get_weight()

        # dump weight data to file as json
        json_filename = weight + '/weight_' + str(int(time.time())) + '.json'
        save_file = open(json_filename, 'w')
        save_file.write(json.dumps(points, default=convert_to_json))
        save_file.close()

        garmindb = GarminDB.GarminDB(db_params_dict)
        for point in points:
            logger.debug("Inserting: " + repr(point))
            GarminDB.Weight.create_or_update(garmindb, point)
        logger.info("DB updated with weight data for %s (%d)" % (str(date), len(points)))


if __name__ == "__main__":
    main(sys.argv[1:])


