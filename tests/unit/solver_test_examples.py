from fractions import Fraction as F

from src.core.order import Order

solve_token_pair_and_fee_token_examples = [
    {
        'b_orders': [
            Order('T0', 'T1', 77012162024712840006, F(1, 5))
        ],
        's_orders': [
            Order('T1', 'T0', 100000000000000, F(1, 10)),
            Order('T1', 'T0', 393154788352361519660, F(51, 10))
        ],
        'f_orders': [
            Order('T0', 'F', 100000000000000, F(1, 10)),
            Order('T0', 'F', 293991938732838123, F(2, 5))
        ]
    }
]

min_average_order_fee_constraint_examples = [
    {
        'b_orders': [
            Order('T0', 'T1', 9000, F(1, 10)),
            Order('T0', 'T1', 9000, F(1, 10)),
            Order('T0', 'T1', 58507, F(1, 5)),
        ],
        's_orders': [
            Order('T1', 'T0', 9000, F(1, 10)),
            Order('T1', 'T0', 196905, F(43, 5)),
            Order('T1', 'T0', 192100, F(4399, 470)),
            Order('T1', 'T0', 113960, F(43, 5))
        ],
        'f_orders': [
            Order('T0', 'F', 9000, F(1, 10)),
            Order('T0', 'F', 9000, F(1, 10)),
            Order('T0', 'F', 10315, F(11, 10))
        ],
        'max_nr_exec_orders': 4
    }
]
