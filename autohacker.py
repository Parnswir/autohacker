import requests
import sys
import time
import logging
import math
import argparse

API_BASE = 'http://localhost:5000/api/'
USERNAME = 'alice@email.com'
PASSWORD = 'alice'
INTERVAL = 3600

config = {}

logger = logging.getLogger('autohacker')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

session = requests.Session()
profileId = ''


def init_argparse():
    parser = argparse.ArgumentParser(
        usage="%(prog)s [-uepiv]",
        description="Become a rich hacker over night."
    )
    parser.add_argument(
        "-v", "--version", action="version",
        version = f"{parser.prog} version 1.0.0"
    )
    parser.add_argument("-u", "--url", help="the API base URL", default=API_BASE)
    parser.add_argument("-e", "--email", help="the user's email", default=USERNAME)
    parser.add_argument("-p", "--password", help="the user's password", default=PASSWORD)
    parser.add_argument("-i", "--interval", help="the refresh interval", type=int, default=INTERVAL)
    return parser


def login():
    response = session.post(config.get('url') + 'login', data={'email': config.get('email'), 'password': config.get('password')})
    global profileId
    profileId = response.json().get('_id')
    logger.info('Connected as %s' % (profileId,))


def get_profile():
    response = session.get(config.get('url') + 'profile')
    return response.json().get('user', {})


def get_bitcoins(user=None):
    if not user:
        user = get_profile()
    return user.get('playerStats', {}).get('bitCoins', 0)


def get_ledger(user=None):
    if not user:
        user = get_profile()
    return user.get('playerStats', {}).get('ledger', 0)


def deposit(amount):
    logger.info('Depositing %d bitcoins...' % (amount,))
    response = session.post(config.get('url') + 'ledger/deposit', data={'depositAmount': amount})
    res = response.json()
    if response.status_code == 200:
        current_deposit = get_ledger(res.get('user'))
        current_bitcoins = get_bitcoins(res.get('user'))
        logger.info('Success. Current deposit: %d \t Current bitcoins: %d' % (current_deposit, current_bitcoins, ))
    else:
        logger.error('Deposit failed', res)


def deposit_all():
    amount = get_bitcoins()
    if amount > 0:
        deposit(amount)


def withdraw(amount):
    logger.info('Withdrawing %d bitcoins...' % (amount,))
    response = session.post(config.get('url') + 'ledger/withdraw', data={'withdrawAmount': amount})
    res = response.json()
    if response.status_code == 200:
        current_deposit = get_ledger(res.get('user'))
        current_bitcoins = get_bitcoins(res.get('user'))
        logger.info('Success. Current deposit: %d \t Current bitcoins: %d' % (current_deposit, current_bitcoins,))
    else:
        logger.error('Withdrawal failed: "%s"' % (res, ))


def withdraw_all():
    amount = get_ledger()
    if amount > 0:
        withdraw(amount)


def get_currencies():
    logger.info('Fetching crypto currency data...')
    response = session.get(config.get('url') + 'currency')
    return response.json().get('currency', [])


def get_rank(user=None):
    if not user:
        user = get_profile()
    return user.get('playerStats', {}).get('rank', 0)


def decorate_currency(c):
    high = c.get('higherPrice', 1)
    low = c.get('lowerPrice', 1)
    c['potential'] = (100 / high) * (high - low)
    c['diff'] = high - low
    return c


def buy(currency, user):
    name = currency.get('name')
    price = currency.get('price', 999999999)
    market_cap = currency.get('marketCap', 0)
    available = currency.get('available', 0)
    max_cash = get_bitcoins(user) + get_ledger(user)
    max_amount = math.floor(max_cash / price)
    already_bought = user.get('currencies', {}).get(name)
    max_available = min(available, 0.2 * market_cap - already_bought)
    amount = min(max_available, max_amount)
    rank = get_rank(user)
    if amount == 0:
        return user
    rank_needed = currency.get('levelReq', 99)
    if rank_needed > rank:
        logger.warning('Buying %s is only possible with rank %d. You are only rank %d.' % (name, rank_needed, rank ))
        return user
    withdraw(max(math.ceil(amount * price) - get_bitcoins(user), 0))
    response = session.post(config.get('url') + 'currency/buy', data={'amount': amount, 'name': name})
    res = response.json()
    if response.status_code == 200:
        user = res.get('user', user)
        cur = user.get('currencies', {}).get(name, 0)
        logger.info('Bought %d %s for %d bitcoins. Current %s deposit: %d' % (amount, name, amount*price, name, cur))
    else:
        logger.error('Failed to buy %s' % (name, ), res)
    deposit_all()
    return get_profile()


def sell(currency, user):
    name = currency.get('name')
    amount = user.get('currencies', {}).get(name)
    if amount == 0:
        logger.warning('Trying to sell %s, but none available!' % (name,))
        return user
    price = currency.get('price', 0)
    response = session.post(config.get('url') + 'currency/sell', data={'amount': amount, 'name': name})
    res = response.json()
    if response.status_code == 200:
        user = res.get('user', user)
        logger.info('Sold %d %s for %d bitcoins.' % (amount, name, amount * price))
    else:
        logger.error('Failed to sell %s' % (name,), res)
    deposit_all()
    return get_profile()


def trade():
    logger.info('Attempting to trade...')
    currencies = list(map(decorate_currency, get_currencies()))
    logger.info('Preparing data for %d currencies...' % (len(currencies),))
    currencies.sort(key=lambda c: c.get('potential'), reverse=True)
    user = get_profile()
    bought_something, sold_something = False, False
    for currency in currencies:
        price = currency.get('price')
        diff = currency.get('diff')
        if price > currency.get('higherPrice') - 0.3 * diff:
            user = sell(currency, user)
            sold_something = True
    if not sold_something:
        logger.info('Nothing to sell...')
    for currency in currencies:
        price = currency.get('price')
        diff = currency.get('diff')
        if price < currency.get('lowerPrice') + 0.3 * diff:
            user = buy(currency, user)
            bought_something = True
    if not bought_something:
        logger.info('Nothing interesting to buy...')
    logger.info('Enough trading for now...')


def earn_battery():
    logger.info('Farming battery...')
    user = get_profile()
    info = user.get('earnBattery', {})
    code_available = False
    for key in ['chessathor', 'megarpg']:
        code = info.get(key, '')
        if code != '':
            code_available = True
            logger.info('Redeeming code "%s" for option "%s"...' % (code, key,))
            res = session.post(config.get('url') + 'earnBattery/redeem', data={ 'code': code })
            if res.status_code == 200:
                logger.info('Success!')
            else:
                logger.error(res['message'])
    if not code_available:
        logger.info('Nothing to redeem...')


def wait():
    logger.info('Sleeping for %d seconds...' % (config.get('interval'),))
    time.sleep(config.get('interval'))


if __name__ == '__main__':
    parser = init_argparse()
    config = vars(parser.parse_args())
    print(config)
    logger.info('Starting autohacker')
    login()
    while True:
        earn_battery()
        trade()
        wait()
