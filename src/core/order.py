"""Class/Functions for handling Order's."""
from copy import copy
from fractions import Fraction as F
from .constants import MIN_TRADABLE_AMOUNT


class Order(object):
    """Class representing an Order."""
    def __init__(
        self,
        index,
        account_id,
        buy_token,
        sell_token,
        max_sell_amount,
        max_xrate
    ):
        self._index = index
        self._account_id = account_id
        self._buy_token = buy_token
        self._sell_token = sell_token
        self._max_sell_amount = max_sell_amount
        self._max_xrate = max_xrate
        self._buy_amount = 0
        self._sell_amount = 0
        self._utility = 0
        self._utility_disreg = 0

    @property
    def index(self):
        return self._index

    @property
    def account_id(self):
        return self._account_id

    @account_id.setter
    def account_id(self, new_account_id):
        self._account_id = new_account_id

    @property
    def buy_token(self):
        return self._buy_token

    @property
    def sell_token(self):
        return self._sell_token

    @property
    def tokens(self):
        return {self._buy_token, self._sell_token}

    @property
    def max_sell_amount(self):
        return self._max_sell_amount

    @max_sell_amount.setter
    def max_sell_amount(self, new_max_sell_amount):
        assert new_max_sell_amount <= self._max_sell_amount
        self._max_sell_amount = new_max_sell_amount

    # This method is equal to the max_sell_amount setter above
    # except it allows the max sell amount to be increased.
    def force_set_max_sell_amount(self, new_max_sell_amount):
        self._max_sell_amount = new_max_sell_amount

    @property
    def max_xrate(self):
        return self._max_xrate

    @property
    def buy_amount(self):
        return self._buy_amount

    @buy_amount.setter
    def buy_amount(self, new_buy_amount):
        self._buy_amount = new_buy_amount

    @property
    def sell_amount(self):
        return self._sell_amount

    @sell_amount.setter
    def sell_amount(self, new_sell_amount):
        self._sell_amount = new_sell_amount

    @property
    def utility(self):
        return self._utility

    @utility.setter
    def utility(self, new_utility):
        self._utility = new_utility

    @property
    def utility_disreg(self):
        return self._utility_disreg

    @utility_disreg.setter
    def utility_disreg(self, new_utility_disreg):
        self._utility_disreg = new_utility_disreg

    @classmethod
    def load_from_dict(cls, index, order_dict):
        buy_amount_ceiled = max(MIN_TRADABLE_AMOUNT, F(order_dict['buyAmount']))
        return Order(
            index=index,
            account_id=order_dict['accountID'],
            buy_token=order_dict['buyToken'],
            sell_token=order_dict['sellToken'],
            max_sell_amount=F(order_dict['sellAmount']),
            max_xrate=F(order_dict['sellAmount']) / buy_amount_ceiled
        )

    def update_order_dict(self, order_dict):
        order_dict['execBuyAmount'] = self.buy_amount
        order_dict['execSellAmount'] = self.sell_amount
        order_dict['utility'] = self.utility
        order_dict['utility_disreg'] = self.utility_disreg

    def with_buy_amount(self, new_buy_amount):
        copy_of_self = copy(self)
        copy_of_self.buy_amount = new_buy_amount
        return copy_of_self

    def with_max_sell_amount(self, new_max_sell_amount):
        copy_of_self = copy(self)
        copy_of_self.max_sell_amount = new_max_sell_amount
        return copy_of_self

    def __str__(self):
        s = f"({self.buy_token}, {self.sell_token}, {self.max_sell_amount}, " \
            f"{self.max_xrate})"
        if self.sell_amount > 0:
            s += f" [{self.buy_amount}, {self.sell_amount}]"
        return s

    def __repr__(self):
        return self.__str__()

    def get_sell_amount_from_buy_amount(
        self, prices, fee, arith_traits
    ):
        """Compute the execSellAmount from execBuyAmount of this order."""
        buy_token_price = prices[self.buy_token]
        sell_token_price = prices[self.sell_token]

        if buy_token_price and sell_token_price:
            xrate = F(buy_token_price, sell_token_price)
            return arith_traits.compute_sell_from_buy_amount(
                buy_amount=self.buy_amount,
                xrate=xrate,
                buy_token_price=buy_token_price,
                fee=fee
            )
        else:
            assert self.buy_amount == 0
            return 0

    def set_sell_amount_from_buy_amount(self, *args, **kwargs):
        """Sets the order sell amount from buy amount so that it satisfies xrate."""
        self._sell_amount = self.get_sell_amount_from_buy_amount(*args, **kwargs)
