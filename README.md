# DEGIRO Portfolio Rebalancer
*Portfolio rebalancing for the finicky investor. A tool that keeps your assets allocation well balanced*

## Disclaimer
This tool is built based on functionalities of the awesome [degiro-connector](https://pypi.org/project/degiro-connector/). This author does not intend to in any way use degiro-connector's own credit to endorse or promote this tool.

This tool is experimental and largely untested, and it may be subject to a frequent state of change. Use this tool at your own risk.

## Quickstart
### Prerequisites
Install [python3](https://www.python.org/downloads/)

Install [poetry](https://python-poetry.org/docs/#installation)

Clone this repo:
```
git clone https://github.com/marcopus/degiro-portfolio-rebalancer.git
```

### Installation 
Install dependencies:
```
poetry install
```

### Configuration
Make a copy of [config_template.json](config/config_template.json) under the [config](config/) directory, give it a name and keep it secret

Open your config file and update `username`, `password`, `reference_date_from`, `reference_date_to`. The from/to dates should capture the interval where the initial investment was made

If your DEGIRO account uses two-step verification, also update the `totp_secret_key` (how? check it out [here](https://github.com/Chavithra/degiro-connector#36-how-to-find-your--totp_secret_key-)), otherwise remove it

### Usage
Run the rebalancer tool:
```
poetry run python degiro_portfolio_rebalancer.py my_account
```
where `my_account` is the name of your json file.

Enjoy!

## Contributing
Contributing to this project is welcome (see [CONTRIBUTING](CONTRIBUTING.md)).
