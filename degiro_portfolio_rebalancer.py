import os
import dateparser as dp
import json
import logging
import pandas as pd
import sys

import degiro_connector.core.helpers.pb_handler as pb_handler
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.trading_pb2 import (
    Credentials,
    ProductsInfo,
    TransactionsHistory,
    Update,
)

TRANSACTION_COSTS = 2.50


def fetch_account_number(username: str, password: str, totp_secret_key: str) -> int:
    """
    Attempts to fetch the account number for the given credentials.
    Returns an integer (account number) or raises a ValueError.
    """
    trading_api = setup_connection(None, username, password, totp_secret_key)

    # fetch the account number
    try:
        return trading_api.get_client_details()["data"]["intAccount"]
    except:
        raise ValueError("Unable to fetch the account number.")


def setup_connection(
    int_account: int, username: str, password: str, totp_secret_key: str, **kwargs
) -> TradingAPI:
    """
    Establishes a connection using the degiro-connector TradingAPI and the current credentials.
    Returns an initialized instance of TradingAPI. Raises ValueError if a connection attempt fails.
    """
    # int_account may be empty here...
    credentials = Credentials(
        int_account=int_account,
        username=username,
        password=password,
        totp_secret_key=totp_secret_key,
    )

    # SETUP TRADING API
    trading_api = TradingAPI(credentials=credentials)

    # CONNECT
    try:
        trading_api.connect()
    except:
        raise ValueError("Unable to establish a connection. Please check credentials.")

    return trading_api


def validate_credentials(config_dict: dict) -> dict:
    """
    Validates the provided credentials, optionally fetches the account number and returns the
    updated credentials. Raises ValueError for any missing data.
    """
    for key in ["username", "password"]:
        if key not in config_dict.keys():
            raise ValueError(f"Missing {key} in credentials provided.")

    if not config_dict.get("int_account"):
        # account number is unknown; fetch it using current config credentials
        config_dict["int_account"] = fetch_account_number(
            config_dict.get("username"),
            config_dict.get("password"),
            config_dict.get("totp_secret_key"),
        )
        print("Your account number:", config_dict["int_account"])

    return config_dict


def read_configuration_from_file(
    account_name: str, config_dirpath: str = "config"
) -> dict:
    """
    Reads a json configuration file for the account named `account_name`.
    Returns a configuration dictionary and the relative path path to the json file.
    """
    config_filepath = os.path.join(config_dirpath, f"{account_name}.json")
    try:
        with open(config_filepath) as config_file:
            config_dict = json.load(config_file)
    except FileNotFoundError as e:
        print(f'ERROR: unable to find a configuration for account "{account_name}"', e)
        sys.exit(1)
    except json.decoder.JSONDecodeError as e:
        print(f'ERROR: unable to decode json file "{account_name}".json')
        sys.exit(1)

    return config_dict


def rebalance(config: dict):
    """
    Fetches account data for the given configuration and prints a rebalancing table.
    """
    config = validate_credentials(config)

    trading_api = setup_connection(**config)

    # SETUP REQUEST TRANSACTIONS
    reference_date_from = dp.parse(
        config.get("reference_date_from"), settings={"DATE_ORDER": "YMD"}
    )
    reference_date_to = dp.parse(
        config.get("reference_date_to"), settings={"DATE_ORDER": "YMD"}
    )
    from_date = TransactionsHistory.Request.Date(
        year=reference_date_from.year,
        month=reference_date_from.month,
        day=reference_date_from.day,
    )
    to_date = TransactionsHistory.Request.Date(
        year=reference_date_to.year,
        month=reference_date_to.month,
        day=reference_date_to.day,
    )
    request = TransactionsHistory.Request(
        from_date=from_date,
        to_date=to_date,
    )

    # FETCH DATA TRANSACTIONS
    transactions_history = trading_api.get_transactions_history(
        request=request,
        raw=False,
    )

    # DISPLAY DATA TRANSACTIONS
    transactions_df = pd.DataFrame(
        [dict(transaction) for transaction in transactions_history.values]
    )
    transactions_df = transactions_df.groupby("productId").agg(
        {"quantity": "sum", "total": "sum"}
    )
    transactions_df.index = transactions_df.index.astype(int).astype(str)
    transactions_df["ratio"] = transactions_df.total / transactions_df.total.sum()

    # SETUP REQUEST PRODUCTS INFO
    request = ProductsInfo.Request()
    request.products.extend([int(id) for id in transactions_df.index])

    # FETCH DATA PRODUCTS INFO
    products_info = trading_api.get_products_info(
        request=request,
        raw=True,
    )
    products_info_df = pd.DataFrame(products_info["data"]).transpose()[
        ["name", "isin", "symbol"]
    ]

    # SETUP REQUEST PORTFOLIO
    request_list = Update.RequestList()
    request_list.values.extend(
        [
            Update.Request(option=Update.Option.PORTFOLIO, last_updated=0),
        ]
    )

    # FETCH DATA PORTFOLIO
    update = trading_api.get_update(request_list=request_list, raw=False)
    update_dict = pb_handler.message_to_dict(message=update)

    # DISPLAY DATA PORTFOLIO
    if "portfolio" not in update_dict:
        raise Exception("No portfolio data!")

    portfolio_df = pd.DataFrame(update_dict["portfolio"]["values"])
    portfolio_df

    # PREPARE PORTFOLIO DATA
    cash = portfolio_df.loc[portfolio_df["positionType"] == "CASH", "value"].sum()
    p = portfolio_df.loc[portfolio_df["positionType"] == "PRODUCT"][
        ["id", "value", "price"]
    ].set_index("id")
    p["ratio"] = p.value / (cash + p.value.sum())
    p = p.merge(
        transactions_df.ratio,
        how="inner",
        left_index=True,
        right_index=True,
        suffixes=("_current", "_initial"),
    )
    p = p.join(products_info_df)

    # CALCULATE PORTFOLIO REBALANCING
    p["buy/sell %"] = (1 - p.ratio_current / p.ratio_initial) * 100
    p["buy/sell"] = p["buy/sell %"] / 100 * p.value
    p["buy/sell units"] = (p["buy/sell"] / p.price).round().astype(int)
    idx_min = p["buy/sell"].idxmin()
    new_portfolio_value = p.value[idx_min] / p.ratio_initial[idx_min]
    p["buy-only"] = new_portfolio_value * p.ratio_initial - p.value
    p["buy-only units"] = (p["buy-only"] / p.price).round().astype(int)
    amount_transaction_buy_sell = -(p["buy/sell units"] * p.price).sum()
    amount_transaction_buy_only = -(p["buy-only units"] * p.price).sum()
    fees_buy_sell = -TRANSACTION_COSTS * (p["buy/sell units"] != 0).sum()
    fees_buy_only = -TRANSACTION_COSTS * (p["buy-only units"] != 0).sum()
    print(p)
    print(
        "\n".join(
            (
                "Amount currently available to trade: €{:.2f}".format(cash),
                "Deposit needed for buy/sell rebalancing: €{:.2f}".format(
                    -min(0, amount_transaction_buy_sell + fees_buy_sell + cash)
                ),
                "Deposit needed for buy-only rebalancing: €{:.2f}".format(
                    -min(0, amount_transaction_buy_only + fees_buy_only + cash)
                ),
            )
        )
    )


if __name__ == "__main__":
    pd.options.display.float_format = "{:.2f}".format

    # SETUP LOGGING LEVEL
    logging.basicConfig(level=logging.ERROR)

    # SETUP CONFIG DICT
    if len(sys.argv) < 2:
        print(
            "Missing account name",
            "Usage: python degiro_portfolio_rebalancer.py <account_name>",
            sep="\n",
        )
        sys.exit(64)

    # READ CONFIGURATION
    config = read_configuration_from_file(sys.argv[1])

    rebalance(config)
