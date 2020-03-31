## Contents

Contains code for finding the optimal exchange rate and buy amounts for
a set of orders and counter-orders between two tokens.

The objective function being optimized here is disregarded utility (2u - umax)
over all orders (same as in the standard solver).

Currently these constraints are taken into account:

* limit exchange rates
* limit sell prices
* uniform clearing price
* token balance
* Sell amount <= account balance
* Min buy/sell amount > 10000
* Max selected orders <= 30

and these are ignored:

* Economic viability

They will be integrated soon.

## Status

All this is still early WIP. Comments are missing and bugs are likely. Code
was tested using the small instances in `data/` *exclusively*.

## Running

For help on all options:
```
python -m src.match -h
```

Running example:
```
python -m src.match solver_greedy/data/token_pair-1-1-1.json token-pair token0 token1
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