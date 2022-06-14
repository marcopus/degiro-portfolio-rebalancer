import unittest

from degiro_portfolio_rebalancer import setup_connection, validate_credentials
from unittest import mock


class TestSetupConnection(unittest.TestCase):
    def setUp(self):
        self.username = "username"
        self.password = "password"
        self.totp_secret_key = "totp_secret_key"

    @mock.patch('degiro_portfolio_rebalancer.Credentials')
    @mock.patch('degiro_portfolio_rebalancer.TradingAPI')
    def test_setup_connection_with_no_account_returns_api(self, MockTradingAPI, MockCredentials):
        api = setup_connection(
            None,
            self.username,
            self.password,
            self.totp_secret_key
        )
        assert api is MockTradingAPI()

    @mock.patch('degiro_portfolio_rebalancer.Credentials')
    @mock.patch('degiro_portfolio_rebalancer.TradingAPI')
    def test_setup_connection_with_account_returns_api(self, MockTradingAPI, MockCredentials):
        api = setup_connection(
            1234567,
            self.username,
            self.password,
            self.totp_secret_key
        )
        assert api is MockTradingAPI()

    @mock.patch('degiro_portfolio_rebalancer.Credentials')
    def test_validate_credentials_fetches_account_number(self, MockCredentials):
        with mock.patch('degiro_portfolio_rebalancer.TradingAPI') as MockTradingAPI:
            trading_api = MockTradingAPI.return_value
            client_details = mock.MagicMock(spec_set=dict)
            client_details.__getitem__.side_effect = lambda name: {'intAccount': 1234567}
            trading_api.get_client_details.return_value = client_details

            config = validate_credentials(
                {
                    'username': self.username,
                    'password': self.password,
                    'totp_secret_key': self.totp_secret_key,
                }
            )
            self.assertEqual(1234567, config['int_account'])
        

if __name__ == '__main__':
    unittest.main()