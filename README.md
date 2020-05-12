## Contents

Contains code for finding the optimal exchange rate and buy amounts for
a set of orders and counter-orders between two tokens.

## Running

For help on all options:
```
python -m src.match -h
```

Example of matching a specific token pair:
```
python -m src.match solver_greedy/data/token_pair-1-1-1.json token-pair token0 token1
```

Example of matching the token pair which leads to higher objective value:
```
python -m src.match solver_greedy/data/token_pair-1-1-1.json best-token-pair
```

## Algorithm

See [here](doc/token_pair/token_pair.pdf).

## Validating results

To validate results, the NLP solver must be used (from dex-solver):

Example:
```
python -m scripts.e2e._run --optModel nlp --jsonFile ../dex-local-sover/data/token_pair-1-1-1.json results/
```

For convenience, all instances in `data/` already include the prices and traded amounts
obtained with the NLP solver.
