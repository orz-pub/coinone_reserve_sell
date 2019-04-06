# -*- coding: utf-8 -*-

import sys
import os
import threading
import datetime
import time
import logging
import logging.handlers
import requests
import json
import click
import base64
import hmac
import hashlib


def read_config(argv):
    if (len(argv) <= 1):
        return None

    with open(argv[1]) as config_file:
        config = json.load(config_file)

    return config


def initialize_logger(config):
    logger = logging.getLogger(os.path.basename(__file__))
    logger.setLevel(config['log_level'])

    formatter = logging.Formatter(config['log_formatter'])

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if config['log_file']:
        file_handler = logging.FileHandler(create_log_file_name())
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def create_log_file_name():
    now = datetime.datetime.now()
    return now.strftime('%Y%m%d_%H%M%S.log')


def work(config, reservation, logger):
    while True:
        try:
            work_complete = work_each(config, reservation, logger)
            if work_complete:
                logger.info("work complete.\n{}".format(reservation))
                return
        except Exception as e:
            logger.error(e)
        finally:
            time.sleep(int(config['refresh_sec']))


def work_each(config, reservation, logger):
    last_price = get_last_price(config, reservation, logger)
    if last_price < 0:
        logger.error("fail get ticker! - {}".format(last_price))
        return False

    if float(reservation['sell_threshold']) >= last_price:
        if 'test_mode' in config:
            if config['test_mode'] and 0 <= float(reservation['sell_margin_price']):
                raise Exception('test mode cannot set positivie sell_margin_price!')

        sell_price = last_price - float(reservation['sell_margin_price'])

        order_id = sell(sell_price, config, reservation, logger)
        if order_id == None:
            logger.error('order_id is None.')
            return False

        max_wait_sell_sec = int(reservation['sell_wait_sec'])
        total_wait_sell_sec = 0
        wait_sell_sec = 10
        while True:
            sell_complete = wait_for_complete_sell(order_id, config, reservation, logger)
            if sell_complete:
                return True

            time.sleep(wait_sell_sec)

            total_wait_sell_sec += wait_sell_sec
            if max_wait_sell_sec <= total_wait_sell_sec:
                logger.warning("elapsed max_wait_sell_sec({}). try cancel sell order...".format(max_wait_sell_sec))

                while cancel_sell(order_id, sell_price, config, reservation, logger) == False:
                    time.sleep(wait_sell_sec)

                logger.warning("complete cancel sell order. {}".format(order_id))
                return False

    return False


def get_last_price(config, reservation, logger):
    get_ticker_url = "{}{}".format(config['ticker_url'], reservation['currency'])

    response = requests.get(get_ticker_url)
    if (response.status_code != 200):
        logger.error("ticker response. code: {}, reason: {}", response.status_code, response.reason)
        return -1

    content = response.content.decode('utf-8')
    ticker = json.loads(content)
    logger.debug(ticker)

    if ticker['result'] != 'success':
        logger.error("ticker result is not success: {}".format(ticker['result']))
        return -2

    last_price = float(ticker['last'])
    if last_price < 0:
        logger.error("ticker negative last: {}".format(last_price))
        return -3

    return last_price


def sell(sell_price, config, reservation, logger):
    encoded_payload = create_sell_payload(sell_price, config, reservation, logger)
    headers = create_https_headers(config, reservation, encoded_payload)

    response = requests.post(config['sell_url'], headers=headers, data=encoded_payload)
    if (response.status_code != 200):
        logger.error("sell response. code: {}, reason: {}", response.status_code, response.reason)
        return None

    content = response.content.decode('utf-8')
    sell_result = json.loads(content)
    logger.info(sell_result)

    if sell_result['errorCode'] != '0':
        logger.error("sell errorCode: {}".format(sell_result['errorCode']))
        return None

    if sell_result['result'] != 'success':
        logger.error("sell result is not success: {}".format(sell_result['result']))
        return None

    return sell_result['orderId']


def create_sell_payload(sell_price, config, reservation, logger):
    payload = {
        'access_token': config['access_token'],
        'currency': reservation['currency'],
        'price': sell_price,
        'qty': float(reservation['sell_quantity'])
        }
    logger.info("sell payload: {}".format(payload))

    encoded_payload = get_encoded_payload(payload)

    return encoded_payload


def get_encoded_payload(payload):
    payload[u'nonce'] = int(time.time() * 1000)
    dumped_json = json.dumps(payload).encode('utf-8')
    encoded_json = base64.b64encode(dumped_json)
    return encoded_json


def create_https_headers(config, reservation, encoded_payload):
    headers = {
        'Content-type': 'application/json',
        'X-COINONE-PAYLOAD': encoded_payload,
        'X-COINONE-SIGNATURE': get_signature(encoded_payload, config['secret_key'])
        }

    return headers


def get_signature(encoded_payload, secret_key):
    signature = hmac.new(secret_key.upper().encode('utf-8'), encoded_payload, hashlib.sha512)
    return signature.hexdigest()


def wait_for_complete_sell(order_id, config, reservation, logger):
    complete_orders = get_complete_orders(config, reservation, logger)

    if complete_orders == None or len(complete_orders) <= 0:
        return False

    for order in complete_orders:
        order_id = order_id.lower()
        if order['orderId'].lower() == order_id:
            logger.debug("find complete order. {}".format(order_id))
            return True

    return False


def get_complete_orders(config, reservation, logger):
    encoded_payload = create_complete_orders_payload(config, reservation)
    headers = create_https_headers(config, reservation, encoded_payload)

    response = requests.post(config['complete_orders_url'], headers=headers, data=encoded_payload)
    if (response.status_code != 200):
        logger.error("complete_orders response. code: {}, reason: {}", response.status_code, response.reason)
        return None

    content = response.content.decode('utf-8')
    complete_orders_result = json.loads(content)
    logger.debug(complete_orders_result)

    if complete_orders_result['errorCode'] != '0':
        logger.error("complete_orders errorCode: {}".format(complete_orders_result['errorCode']))
        return None

    if complete_orders_result['result'] != 'success':
        logger.error("complete_orders result is not success: {}".format(complete_orders_result['result']))
        return None

    return complete_orders_result['completeOrders']


def create_complete_orders_payload(config, reservation):
    payload = {
        'access_token': config['access_token'],
        'currency': reservation['currency']
        }

    encoded_payload = get_encoded_payload(payload)

    return encoded_payload


def cancel_sell(order_id, sell_price, config, reservation, logger):
    encoded_payload = create_cancel_order_payload(order_id, sell_price, config, reservation, logger)
    headers = create_https_headers(config, reservation, encoded_payload)

    response = requests.post(config['cancel_order_url'], headers=headers, data=encoded_payload)
    if (response.status_code != 200):
        logger.error("sell response. code: {}, reason: {}", response.status_code, response.reason)
        return False

    content = response.content.decode('utf-8')
    cancel_result = json.loads(content)
    logger.info(cancel_result)

    if cancel_result['errorCode'] != '0':
        logger.error("sell errorCode: {}".format(cancel_result['errorCode']))
        return False

    if cancel_result['result'] != 'success':
        logger.error("sell result is not success: {}".format(cancel_result['result']))
        return False

    return True


def create_cancel_order_payload(order_id, sell_price, config, reservation, logger):
    payload = {
        'access_token': config['access_token'],
        'currency': reservation['currency'],
        'order_id': order_id,
        'price': sell_price,
        'qty': float(reservation['sell_quantity']),
        'is_ask': 1
        }

    logger.info("cancel sell payload: {}".format(payload))

    encoded_payload = get_encoded_payload(payload)

    return encoded_payload


def main(argv):
    config = read_config(argv)
    if config == None:
        print("usage:\n\t{} config.json".format(os.path.basename(__file__)))
        return

    logger = initialize_logger(config)
    pretty_config = json.dumps(config, indent=4)
    if (click.confirm("please check config...\n\n{}\n\ncontinue?".format(pretty_config),
                      default=False)) == False:
        logger.info('user canceled.')
        return

    for reservation in config['reservation']:
        thread = threading.Thread(target=work, args=(config, reservation, logger))
        thread.start()


if __name__ == "__main__":
    main(sys.argv)
