# Intentional divergences from hummingbot core

These are intentional divergences from hummingbot core carried by `data_type_primitives`,
inherited from hb-order-book `docs/divergences.md` @ 9718f7d.

Rule: contract parity, not defect parity. The package matches core's observable contract
and deliberately does not reproduce core defects. Tests asserting a divergence carry
`@pytest.mark.divergence`, so a run against core can deselect or xfail them
(`-m "not divergence"`). Paths are relative to `hummingbot/core/data_type/`.

| # | Divergence | Core location | Rationale |
|---|---|---|---|
| 1 | `OrderBookMessage.__hash__` hashes the tuple `(type, id)` | `order_book_message.py:82` | Core calls `hash(a, b, c)`, which always raises `TypeError`. |
| 2 | `OrderBookMessage.__lt__` / `__eq__` are strict (irreflexive, consistent) | `order_book_message.py:75-79`, `:84-93` | In `__lt__` the trailing `or self.has_update_id` sits outside the equal-timestamp branch, so a snapshot or diff is `<` anything. `restore_from_snapshot_and_diffs` (`order_book.pyx:479`) then gets `bisect_right == 0` and replays stale diffs. `__eq__` falls through to `trade_id` (-1 == -1), so DIFFs with different `update_id` compare equal. |
| 3 | `InFlightOrder.is_filled` / `is_done` use an exact Decimal comparison (`executed_amount_base >= amount`), so dust remainders are no longer reported filled/done | `in_flight_order.py` `is_filled` / `is_done` | Core uses float `math.isclose` (rel_tol 1e-9) on Decimal amounts, which misreports partially filled orders (hb-data-type-primitives#47, reported by hb-market-connector#211). |
| 4 | dtp-only `OrderState.UNKNOWN = 11` (open, not done, not processed by exchange) | `in_flight_order.py` `OrderState` / `is_open` / `check_processed_by_exchange_condition` | Core has no state for an order whose create response was lost; it fails it, so a possibly-live order can be re-placed (hb-data-type-primitives#48, requested by hb-market-connector#214). Core code with explicit state lists (`client_order_tracker`) does not know it, and persisted `last_state=11` is unreadable by non-dtp hummingbot. |

## Draft core bug report (not filed)

Three defects in `hummingbot/core/data_type/order_book_message.py`.

```python
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

def diff(uid, ts):
    return OrderBookMessage(OrderBookMessageType.DIFF, {"update_id": uid}, ts)

def snap(uid, ts):
    return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {"update_id": uid}, ts)

# 1. __lt__: a snapshot/diff is less than everything, including itself and older messages.
assert snap(10, 1.0) < diff(9, 0.5)      # passes, expected False (id 10 > 9, older ts)
assert diff(1, 1.0) < diff(1, 1.0)       # passes, expected False

# 1b. Consequence: OrderBook.restore_from_snapshot_and_diffs uses bisect_right(diffs, snapshot).
#     Since diff < snapshot is always True... and snapshot < diff is also True, the
#     bisect result is 0, so diffs with update_id <= snapshot.update_id are replayed.

# 2. __eq__: for non-trade messages the trade_id fall-through (-1 == -1) makes
#    DIFFs with different update_id equal.
assert diff(1, 1.0) == diff(2, 1.0)      # passes, expected False

# 3. __hash__: hash() takes one argument.
hash(diff(1, 1.0))                       # TypeError: hash() takes exactly one argument (3 given)
```

Suggested fix: move `or self.has_update_id` inside the equal-timestamp branch of `__lt__`,
guard the `trade_id` branch of `__eq__` with `not self.has_update_id`, and use
`hash((self.type, self.update_id, self.trade_id))`.
