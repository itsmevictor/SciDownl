"""Optional browser handoff for verification that requires user interaction."""
from ..log import get_logger

logger = get_logger()


def fetch_verified_page(url, session, proxies):
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as error:
        raise RuntimeError(
            'Browser mode requires Selenium. Install the browser extra from the '
            'project directory: python3 -m pip install -e ".[browser]"') from error

    options = webdriver.ChromeOptions()
    proxy = proxies.get('https') or proxies.get('http')
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')
    logger.info('Opening Chrome. Complete the robot check in the browser; '
                'the download will resume automatically (waiting up to 3 minutes).')
    with webdriver.Chrome(options=options) as browser:
        browser.set_page_load_timeout(30)
        browser.get(url)
        WebDriverWait(browser, 180).until(lambda driver: driver.find_elements(
            By.CSS_SELECTOR,
            'meta[name="citation_pdf_url"], div.pdf object[data], embed#pdf[src], '
            'iframe#pdf[src], object[type="application/pdf"][data], '
            'iframe[src*=".pdf"], a[href*=".pdf"]'))
        session.headers['User-Agent'] = browser.execute_script('return navigator.userAgent')
        for cookie in browser.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'],
                                path=cookie.get('path', '/'), secure=cookie.get('secure', False),
                                expires=cookie.get('expiry'))
        return browser.page_source, browser.current_url
