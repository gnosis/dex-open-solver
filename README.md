## Contents

Contains code for finding the optimal exchange rate and buy amounts for
a set of orders and counter-orders between two tokens.

The objective function being optimized here is disregarded utility (2u - umax)
over all orders (same as in the standard solver).

Only the base constraints are taken into account:

* limit exchange rates
* limit sell prices
* uniform clearing price
* token balance

meaning that there are many which are ignored, such as:

* Sell amount <= account balance
* Min buy/sell amount > 10000
* Max selected orders <= 30
* Economic viability
* etc, etc

Trying to integrate these was not attempted yet. It might turn
out that it can be done for some of them without loosing optimality guarantees,
but I wouldn't bet on that.

## Status

All this is very early WIP. Comments are missing and bugs are likely. Code
was tested using the small instances in `data/` *exclusively*.

Currently the code just prints the optimal exchange rate and traded amounts as
rational numbers. 

TODO:

* To actually generate the output solution json, it is necessary to recompute the
traded amounts using the integer arithmetic done in the smart contract. There is
some code for that, but it's not enabled.

## Running

For help on all options:
```
python -m src.main -h
```

Running example:
```
python -m src.main solver_greedy/data/token_pair-1-1-1.json token0 token1
```

## Validating results

To validate results, the NLP solver must be used (from dex-solver):

Example:
```
python -m scripts.e2e._run --optModel nlp --jsonFile ../dex-local-sover/data/token_pair-1-1-1.json results/
```

For convenience, all instances in `data/` already include the prices and traded amounts
obtained with the NLP solver.

# Development

There is a jupyter notebook that plots pairwise instances, the objective function, and the local/global optima
found by the algorithm. An example is in `doc/obj_zoo.pdf`.