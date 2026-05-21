# hb-data-type-primitives

[![CI](https://github.com/MementoRC/hb-data-type-primitives/actions/workflows/ci.yml/badge.svg)](https://github.com/MementoRC/hb-data-type-primitives/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MementoRC/hb-data-type-primitives)](https://codecov.io/gh/MementoRC/hb-data-type-primitives)
[![PyPI version](https://badge.fury.io/py/hb-data-type-primitives.svg)](https://badge.fury.io/py/hb-data-type-primitives)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Common data type primitives (validated models) for Hummingbot sub-packages.

## Overview

This package provides validated data type primitives — enums, dataclasses, and Pydantic
models — used across Hummingbot sub-packages. It is a future sibling dependency for
`hb-connector-utils` and `hb-event-bus`.

> **Scaffold notice**: This repository is in initial standardization state. The
> `data_type_primitives` module contains only the package scaffold. Domain code will
> be added in subsequent PRs.

## Installation

```bash
pip install hb-data-type-primitives
```

Or with pixi:

```bash
pixi add hb-data-type-primitives
```

## Usage

```python
import data_type_primitives
```
