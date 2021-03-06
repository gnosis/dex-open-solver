from fractions import Fraction as F

from dex_open_solver.core.order import Order

find_best_xrate_examples = [
    {
        'b_orders': [
            Order('T0', 'T1', 5942260566990937138846, F(2, 15)),
            Order('T0', 'T1', 100000000000000, F(2, 15))
        ],
        's_orders': [
            Order('T1', 'T0', 53584344584028329569112, F(90059, 9985))
        ]
    },
    {
        'b_orders': [
            Order('T0', 'T1', 100000000000000, F(21, 10)),
            Order('T0', 'T1', 100000000000000, F(21, 10)),
            Order('T0', 'T1', 100000000000000, F(61, 30))
        ],
        's_orders': [
            Order('T1', 'T0', 100000000000000, F(7039, 6620))
        ]
    },
    {
        'b_orders': [
            Order('T0', 'T1', 100000000000000, F(269, 125)),
            Order('T0', 'T1', 100000000000000, F(2906, 1655)),
            Order('T0', 'T1', 100000000000000, F(2906, 1655))
        ],
        's_orders': [
            Order('T1', 'T0', 100000000000000, 2)
        ]
    },
    {
        'b_orders': [
            Order('T0', 'T1', 100000000000000, F(21, 10)),
            Order('T0', 'T1', 100000000000000, F(21, 10)),
            Order('T0', 'T1', 100000000000000, F(61, 30))
        ],
        's_orders': [
            Order('T1', 'T0', 100000000000000, F(7033, 6620))
        ]
    },
    {
        'b_orders': [
            Order('T0', 'T1', 100000000000000, F(2037, 6620))
        ],
        's_orders': [
            Order('T1', 'T0', 100000000000000, F(259, 30)),
            Order('T1', 'T0', 100000000000000, F(63539, 6620))
        ]
    }
]
