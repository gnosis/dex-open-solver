import json
import logging
from collections import namedtuple
from fractions import Fraction as F
from .order_util import IntegerTraits
from .orderbook import compute_objective_values
from .util import stringify_numeric

logger = logging.getLogger(__name__)

Fee = namedtuple('Fee', ['token', 'value'])


def load_fee(fee_dict):
    return Fee(token=fee_dict['token'], value=F(fee_dict['ratio']))


def dump_solution(
    instance,
    solution_file,
    orders,
    prices,
    fee,
    arith_traits=IntegerTraits
):
    # Dump prices.
    instance['prices'] = prices

    # Update accounts.
    accounts = instance['accounts']
    for order in orders:
        account_id = order.account_id
        buy_token = order.buy_token
        sell_token = order.sell_token
        if order.buy_token not in accounts[account_id]:
            accounts[account_id][order.buy_token] = 0
        accounts[account_id][buy_token] = int(accounts[account_id][buy_token])
        accounts[account_id][sell_token] = int(accounts[account_id][sell_token])
        accounts[account_id][buy_token] += order.buy_amount
        accounts[account_id][sell_token] -= order.sell_amount

    # Dump objective info.
    instance['objVals'] = compute_objective_values(prices, accounts, orders, fee)

    # Dump touched orders.
    orders = sorted(orders, key=lambda order: order.index)
    orders_indexes = {order.index for order in orders}
    original_orders = [
        order for index, order in enumerate(instance['orders'])
        if index in orders_indexes
    ]
    touched_orders = []
    for order, original_order in zip(orders, original_orders):
        if order.sell_amount > 0:
            original_order['execSellAmount'] = str(order.sell_amount)
            original_order['execBuyAmount'] = str(order.buy_amount)
            touched_orders.append(original_order)
    instance['orders'] = touched_orders

    # Restore fee as a float (is Decimal).
    instance['fee']['ratio'] = float(instance['fee']['ratio'])

    # Dump json.
    instance = stringify_numeric(instance)
    for order in instance['orders']:
        if 'orderID' in order.keys():
            order['orderID'] = int(order['orderID'])
    json.dump(instance, solution_file, indent=4)
