from fractions import Fraction as F

from dex_open_solver.core.order import Order

max_nr_orders_constraint_examples = [
    {
        'b_orders': [
            Order('T0', 'T1', 20019, F(3, 10))
        ],
        's_orders': [
            Order('T1', 'T0', 50096, F(51, 10)),
            Order('T1', 'T0', 50096, F(16567, 3310))
        ],
        'xrate': F(1, 5),
        'max_nr_exec_orders': 2
    }
]


min_tradable_amount_constraint_examples = [
    {
        'b_orders': [
            Order('T0', 'T1', 10009, F(313, 330)),
            Order('T0', 'T1', 136536, F(1))
        ],
        's_orders': [
            Order('T1', 'T0', 9000, F(1, 10)),
            Order('T1', 'T0', 9000, F(1, 10)),
            Order('T1', 'T0', 21481, F(11, 10)),
            Order('T1', 'T0', 123177, F(11, 10))
        ],
        'xrate': F(61144, 64715),
        'max_nr_exec_orders': 4
    }
]
