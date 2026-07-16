from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

from ._trading_pair import combine_to_hb_trading_pair, split_hb_trading_pair
from .common import PositionAction, TradeType

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# Structural (Protocol) collaborators.
#
# data_type_primitives is an ADR-0001 L0 leaf and must not import hummingbot
# (enforced by the data-type-primitives-boundary and
# adr-0001-l0-leaf-independence import-linter contracts). We therefore describe
# the collaborators we need by shape rather than importing their concrete
# hummingbot classes.
# ---------------------------------------------------------------------------
class RateSource(Protocol):
    """Anything able to resolve a conversion rate for a trading pair.

    Satisfied by hummingbot's ``RateOracle`` in the full runtime.
    """

    def get_pair_rate(self, trading_pair: str) -> Decimal | None: ...


class ExchangeLike(Protocol):
    """Minimal exchange surface needed to price fee tokens (hummingbot ExchangeBase)."""

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal: ...


class OrderCandidateLike(Protocol):
    """Structural view of a hummingbot ``OrderCandidate`` used for fee-impact math."""

    order_collateral: Any
    potential_returns: Any

    def get_size_token_and_order_size(self) -> tuple[str, Decimal]: ...


# Optional default rate source. L0 purity forbids importing hummingbot's
# RateOracle here, so the full runtime opts in by registering a provider, e.g.:
#     set_default_rate_source_provider(lambda: RateOracle.get_instance())
_default_rate_source_provider: Callable[[], RateSource] | None = None


def set_default_rate_source_provider(
    provider: Callable[[], RateSource] | None,
) -> None:
    """Register (or clear) the default rate source used when no rate_source is passed."""
    global _default_rate_source_provider
    _default_rate_source_provider = provider


S_DECIMAL_0 = Decimal(0)


@dataclass
class TokenAmount:
    token: str
    amount: Decimal

    def __iter__(self):
        return iter((self.token, self.amount))

    def to_json(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "amount": str(self.amount),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]):
        instance = TokenAmount(token=data["token"], amount=Decimal(data["amount"]))
        return instance


@dataclass
class TradeFeeSchema:
    """
    Contains the necessary information to build a `TradeFee` object.

    NOTE: Currently, `percent_fee_token` is only specified if the percent fee is always
    charged in a particular token (e.g. the Binance BNB case). To always populate the
    `percent_fee_token`, this class will require access to the `exchange` class at runtime
    to determine the collateral token for the trade (e.g. for derivatives).
    This means that, if the `percent_fee_token` is specified, then the fee is always added
    to the trade costs, and `buy_percent_fee_deducted_from_returns` cannot be set to `True`.
    """

    percent_fee_token: str | None = None
    maker_percent_fee_decimal: Decimal = S_DECIMAL_0
    taker_percent_fee_decimal: Decimal = S_DECIMAL_0
    buy_percent_fee_deducted_from_returns: bool = False
    maker_fixed_fees: list[TokenAmount] = field(default_factory=list)
    taker_fixed_fees: list[TokenAmount] = field(default_factory=list)

    def __post_init__(self):
        self.validate_schema()

    def validate_schema(self):
        if self.percent_fee_token is not None:
            assert not self.buy_percent_fee_deducted_from_returns
        self.maker_percent_fee_decimal = Decimal(self.maker_percent_fee_decimal)
        self.taker_percent_fee_decimal = Decimal(self.taker_percent_fee_decimal)
        for i in range(len(self.taker_fixed_fees)):
            self.taker_fixed_fees[i] = TokenAmount(
                self.taker_fixed_fees[i].token, Decimal(self.taker_fixed_fees[i].amount)
            )
        for i in range(len(self.maker_fixed_fees)):
            self.maker_fixed_fees[i] = TokenAmount(
                self.maker_fixed_fees[i].token, Decimal(self.maker_fixed_fees[i].amount)
            )


@dataclass
class TradeFeeBase(ABC):
    """
    Contains the necessary information to apply the trade fee to a particular order.
    """

    percent: Decimal = S_DECIMAL_0
    percent_token: str | None = (
        None  # only set when fee charged in third token (the Binance BNB case)
    )
    flat_fees: list[TokenAmount] = field(default_factory=list)  # list of (asset, amount) tuples

    @classmethod
    @abstractmethod
    def type_descriptor_for_json(cls) -> str: ...

    @classmethod
    def fee_class_for_type(cls, type_descriptor: str):
        catalog = {
            fee_class.type_descriptor_for_json(): fee_class
            for fee_class in [AddedToCostTradeFee, DeductedFromReturnsTradeFee]
        }
        return catalog[type_descriptor]

    @classmethod
    def new_spot_fee(
        cls,
        fee_schema: TradeFeeSchema,
        trade_type: TradeType,
        percent: Decimal = S_DECIMAL_0,
        percent_token: str | None = None,
        flat_fees: list[TokenAmount] | None = None,
    ) -> TradeFeeBase:
        fee_cls: type[TradeFeeBase] = (
            AddedToCostTradeFee
            if (
                trade_type == TradeType.BUY
                and (
                    not fee_schema.buy_percent_fee_deducted_from_returns
                    or fee_schema.percent_fee_token is not None
                )
            )
            else DeductedFromReturnsTradeFee
        )
        return fee_cls(percent=percent, percent_token=percent_token, flat_fees=flat_fees or [])

    @classmethod
    def new_perpetual_fee(
        cls,
        fee_schema: TradeFeeSchema,
        position_action: PositionAction,
        percent: Decimal = S_DECIMAL_0,
        percent_token: str | None = None,
        flat_fees: list[TokenAmount] | None = None,
    ) -> TradeFeeBase:
        fee_cls: type[TradeFeeBase] = (
            AddedToCostTradeFee
            if position_action == PositionAction.OPEN or fee_schema.percent_fee_token is not None
            else DeductedFromReturnsTradeFee
        )
        return fee_cls(percent=percent, percent_token=percent_token, flat_fees=flat_fees or [])

    @classmethod
    def from_json(cls, data: dict[str, Any]):
        fee_class = cls.fee_class_for_type(data["fee_type"])
        instance = fee_class(
            percent=Decimal(data["percent"]),
            percent_token=data["percent_token"],
            flat_fees=list(map(TokenAmount.from_json, data["flat_fees"])),
        )
        return instance

    def to_json(self) -> dict[str, any]:
        return {
            "fee_type": self.type_descriptor_for_json(),
            "percent": str(self.percent),
            "percent_token": self.percent_token,
            "flat_fees": [token_amount.to_json() for token_amount in self.flat_fees],
        }

    @property
    def fee_asset(self):
        first_flat_fee_token = None
        if len(self.flat_fees) > 0:
            first_flat_fee_token = self.flat_fees[0].token
        return self.percent_token or first_flat_fee_token

    @abstractmethod
    def get_fee_impact_on_order_cost(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> TokenAmount | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        ...

    @abstractmethod
    def get_fee_impact_on_order_returns(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> Decimal | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        ...

    @staticmethod
    def _get_exchange_rate(
        trading_pair: str,
        rate_source: RateSource | None = None,
    ) -> Decimal:
        local_rate_source: RateSource | None = rate_source
        if local_rate_source is None and _default_rate_source_provider is not None:
            local_rate_source = _default_rate_source_provider()
        if local_rate_source is None:
            raise ValueError(
                f"Could not resolve a rate source for {trading_pair}. Pass a rate_source "
                f"or register one via set_default_rate_source_provider()."
            )
        rate: Decimal | None = local_rate_source.get_pair_rate(trading_pair)
        if rate is None:
            raise ValueError(
                f"Could not find the exchange rate for {trading_pair} using the rate source "
                f"{local_rate_source} (please verify it has been correctly configured)"
            )
        return rate

    def fee_amount_in_token(
        self,
        trading_pair: str,
        price: Decimal,
        order_amount: Decimal,
        token: str,
        rate_source: RateSource | None = None,
    ) -> Decimal:
        base, quote = split_hb_trading_pair(trading_pair)
        fee_amount: Decimal = S_DECIMAL_0
        if self.percent != S_DECIMAL_0:
            amount_from_percentage: Decimal = (price * order_amount) * self.percent
            if self._are_tokens_interchangeable(quote, token):
                fee_amount += amount_from_percentage
            else:
                conversion_rate: Decimal = self._get_exchange_rate(trading_pair, rate_source)
                # Protect against division by zero - use trade price as fallback if rate is 0
                if conversion_rate == S_DECIMAL_0:
                    conversion_rate = price if price > S_DECIMAL_0 else Decimal("1")
                fee_amount += amount_from_percentage / conversion_rate
        for flat_fee in self.flat_fees:
            if self._are_tokens_interchangeable(flat_fee.token, token):
                # No need to convert the value
                fee_amount += flat_fee.amount
            elif self._are_tokens_interchangeable(flat_fee.token, base) and (
                self._are_tokens_interchangeable(quote, token)
            ):
                # Use price directly instead of looking up the rate
                fee_amount += flat_fee.amount * price
            else:
                conversion_pair: str = combine_to_hb_trading_pair(base=flat_fee.token, quote=token)
                conversion_rate: Decimal = self._get_exchange_rate(conversion_pair, rate_source)
                fee_amount += flat_fee.amount * conversion_rate
        return fee_amount

    def _are_tokens_interchangeable(self, first_token: str, second_token: str):
        interchangeable_tokens = [
            {"WETH", "ETH"},
            {"WBNB", "BNB"},
            {"WPOL", "POL"},
            {"WAVAX", "AVAX"},
            {"WONE", "ONE"},
            {"USDC", "USDC.E"},
            {"WBTC", "BTC"},
            {"USOL", "SOL"},
            {"UETH", "ETH"},
            {"UBTC", "BTC"},
        ]
        return first_token == second_token or any(
            {first_token, second_token} <= interchangeable_pair
            for interchangeable_pair in interchangeable_tokens
        )


class AddedToCostTradeFee(TradeFeeBase):
    @classmethod
    def type_descriptor_for_json(cls) -> str:
        return "AddedToCost"

    def get_fee_impact_on_order_cost(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> TokenAmount | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        ret = None
        if self.percent != S_DECIMAL_0:
            fee_token = self.percent_token or order_candidate.order_collateral.token
            if (
                order_candidate.order_collateral is None
                or fee_token != order_candidate.order_collateral.token
            ):
                token, size = order_candidate.get_size_token_and_order_size()
                if fee_token == token:
                    exchange_rate = Decimal("1")
                else:
                    exchange_pair = combine_to_hb_trading_pair(
                        token, fee_token
                    )  # buy order token w/ pf token
                    exchange_rate = exchange.get_price(exchange_pair, is_buy=True)
                fee_amount = size * exchange_rate * self.percent
            else:  # self.percent_token == order_candidate.order_collateral.token
                fee_amount = order_candidate.order_collateral.amount * self.percent
            ret = TokenAmount(fee_token, fee_amount)
        return ret

    def get_fee_impact_on_order_returns(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> Decimal | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        return None


class DeductedFromReturnsTradeFee(TradeFeeBase):
    @classmethod
    def type_descriptor_for_json(cls) -> str:
        return "DeductedFromReturns"

    def get_fee_impact_on_order_cost(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> TokenAmount | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the cost requirements for the candidate order.
        """
        return None

    def get_fee_impact_on_order_returns(
        self, order_candidate: OrderCandidateLike, exchange: ExchangeLike
    ) -> Decimal | None:
        """
        WARNING: Do not use this method for sizing. Instead, use the `BudgetChecker`.

        Returns the impact of the fee on the expected returns from the candidate order.
        """
        impact = order_candidate.potential_returns.amount * self.percent
        return impact


@dataclass(frozen=True)
class MakerTakerExchangeFeeRates:
    maker: Decimal
    taker: Decimal
    maker_flat_fees: list[TokenAmount]
    taker_flat_fees: list[TokenAmount]
