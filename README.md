## Contents

This package contains code for finding the optimal exchange rate and trade amounts
for a set of orders between two tokens.

## Installing

```bash
pip install dex-open-solver
```

or

```bash
pip install git+http://github.com/gnosis/dex-open-solver#egg=dex-open-solver
```

## Using

For help on all options:
```
gp_match -h
```

Matching a specific token pair:
```
gp_match instance.json token-pair token0 token1
```

Matching the token pair which leads to highest objective value:
```
gp_match instance.json best-token-pair
```

## Developing

1. Checkout the source code.

```bash
git clone git@github.com:gnosis/dex-open-solver.git
cd dex-open-solver
```

2. Create a virtual environment (optional but recommended):

```bash
virtualenv --python=/usr/bin/python3 venv
. venv/bin/activate
```

3. Install in development mode:
```bash
pip install -e .
```

## Algorithm

See [here](doc/token_pair/token_pair.pdf).
