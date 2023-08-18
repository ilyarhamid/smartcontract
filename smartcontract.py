from web3 import Web3
from web3.contract.contract import ContractFunction
import json
from web3.types import (
    TxParams,
    Wei,
    Nonce
)

def load_abi(file_path: str) -> str:
    with open(file_path) as f:
        abi: str = json.load(f)
    return abi

class SmartContract():
    def __init__(self, rpc_link, address, abi_path, wallet_credentials=None):
        self.rpc_link = rpc_link
        self.address = address
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_link))
        self.contract = self.w3.eth.contract(address=self.address, abi=load_abi(abi_path))
        self.token_abi = load_abi("./abi.json")
        self.wallet_credentials = wallet_credentials
        if self.wallet_credentials:
            try:
                self.wallet_address = wallet_credentials['wallet_address']
                self.wallet_secret = wallet_credentials['wallet_secret']
                self.last_nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            except ValueError:
                raise Exception(f"Wallet address {self.wallet_address} is not a valid wallet.")

    def call_read_function(self, func_name, params={}):
        f = getattr(self.contract.functions, func_name)
        return f(**params).call()

    def call_write_function(self, func_name, params={}, value: Wei = Wei(0)):
        if not self.wallet_credentials:
            print("Can not write functions without wallet credentials")
        f = getattr(self.contract.functions, func_name)(**params)
        tx = self.execute(f, tx_params=self.get_tx_params(value=value))
        return tx.hex()
            
    def get_gas_price(self):
        return int(self.w3.eth.gas_price)

    def get_tx_params(self, value, gas: Wei = Wei(350000)) -> TxParams:
        gasprice = self.get_gas_price()
        return {
            "from": self.w3.to_checksum_address(self.wallet_address),
            "value": value,
            "gas": gas,
            "gasPrice": gasprice,
            "nonce": max(
                self.last_nonce, self.w3.eth.get_transaction_count(self.wallet_address)
            ),
            "chainId": self.w3.eth.chain_id
        }    
        
    def execute(self, function: ContractFunction, tx_params):
        transaction = function.build_transaction(tx_params)
        signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key=self.wallet_secret)
        try:
            return self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        finally:
            self.last_nonce = Nonce(tx_params["nonce"] + 1)    
    
    def approve_token(self, token_address):
        token_contract = self.w3.eth.contract(self.w3.to_checksum_address(token_address), abi=self.token_abi)
        allowance = token_contract.functions.allowance(self.wallet_address, self.address).call()
        if allowance == 0:
            approval = token_contract.functions.approve(self.address, int(2 ** 256 -1))
            gasprice = self.get_gas_price()
            return self.execute(approval, tx_params=self.get_tx_params(value=Wei(0))).hex()