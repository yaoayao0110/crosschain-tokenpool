"""
Web3 connection and contract interaction manager
"""
import logging
from typing import Dict, Optional, Any, Tuple
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound, BlockNotFound
from eth_account import Account
from hexbytes import HexBytes
import time

try:
    from .config import config, ChainConfig
except ImportError:
    from config import config, ChainConfig

logger = logging.getLogger(__name__)

class Web3Manager:
    """Manages Web3 connections and contract interactions for multiple chains"""
    
    def __init__(self):
        self.connections: Dict[str, Web3] = {}
        self.contracts: Dict[str, Contract] = {}
        self.accounts: Dict[str, Any] = {}
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize Web3 connections for all configured chains"""
        for chain_name, chain_config in config.CHAINS.items():
            try:
                # Create Web3 connection
                w3 = Web3(Web3.HTTPProvider(chain_config.rpc_url))
                
                # Test connection
                if not w3.is_connected():
                    logger.error(f"Failed to connect to {chain_name} at {chain_config.rpc_url}")
                    continue
                
                self.connections[chain_name] = w3
                
                # Initialize contract if address is provided
                if chain_config.contract_address:
                    contract = w3.eth.contract(
                        address=chain_config.contract_address,
                        abi=config.CONTRACT_ABI
                    )
                    self.contracts[chain_name] = contract
                
                # Initialize manager account
                if config.CROSS_CHAIN.manager_private_key:
                    account = Account.from_key(config.CROSS_CHAIN.manager_private_key)
                    self.accounts[chain_name] = account
                
                logger.info(f"Initialized {chain_name} connection successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize {chain_name}: {str(e)}")
    
    def get_web3(self, chain: str) -> Optional[Web3]:
        """Get Web3 instance for a chain"""
        return self.connections.get(chain)
    
    def get_contract(self, chain: str) -> Optional[Contract]:
        """Get contract instance for a chain"""
        return self.contracts.get(chain)
    
    def get_account(self, chain: str) -> Optional[Any]:
        """Get account for a chain"""
        return self.accounts.get(chain)
    
    def get_latest_block(self, chain: str) -> Optional[int]:
        """Get latest block number for a chain"""
        w3 = self.get_web3(chain)
        if not w3:
            return None
        
        try:
            return w3.eth.block_number
        except Exception as e:
            logger.error(f"Failed to get latest block for {chain}: {str(e)}")
            return None
    
    def get_transaction_receipt(self, chain: str, tx_hash: str) -> Optional[Dict]:
        """Get transaction receipt"""
        w3 = self.get_web3(chain)
        if not w3:
            return None
        
        try:
            return w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get transaction receipt for {tx_hash} on {chain}: {str(e)}")
            return None
    
    def wait_for_transaction(self, chain: str, tx_hash: str, timeout: int = 300) -> Optional[Dict]:
        """Wait for transaction to be mined"""
        w3 = self.get_web3(chain)
        if not w3:
            return None
        
        try:
            return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        except Exception as e:
            logger.error(f"Failed to wait for transaction {tx_hash} on {chain}: {str(e)}")
            return None
    
    def send_transaction(self, chain: str, transaction: Dict) -> Optional[str]:
        """Send a transaction"""
        w3 = self.get_web3(chain)
        account = self.get_account(chain)
        
        if not w3 or not account:
            logger.error(f"Missing Web3 connection or account for {chain}")
            return None
        
        try:
            # Get nonce
            nonce = w3.eth.get_transaction_count(account.address)
            
            # Prepare transaction
            transaction.update({
                'nonce': nonce,
                'from': account.address,
                'chainId': config.CHAINS[chain].chain_id
            })
            
            # Estimate gas if not provided
            if 'gas' not in transaction:
                try:
                    gas_estimate = w3.eth.estimate_gas(transaction)
                    transaction['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
                except Exception as e:
                    logger.warning(f"Gas estimation failed: {str(e)}, using default")
                    transaction['gas'] = 200000
            
            # Set gas price if not provided
            if 'gasPrice' not in transaction:
                transaction['gasPrice'] = w3.eth.gas_price
            
            # Sign and send transaction
            signed_txn = w3.eth.account.sign_transaction(transaction, account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"Transaction sent on {chain}: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to send transaction on {chain}: {str(e)}")
            return None
    
    def call_contract_function(self, chain: str, function_name: str, *args, **kwargs) -> Any:
        """Call a contract function (read-only)"""
        contract = self.get_contract(chain)
        if not contract:
            logger.error(f"No contract found for {chain}")
            return None
        
        try:
            function = getattr(contract.functions, function_name)
            return function(*args, **kwargs).call()
        except Exception as e:
            logger.error(f"Failed to call {function_name} on {chain}: {str(e)}")
            return None
    
    def build_transaction(self, chain: str, function_name: str, *args, **kwargs) -> Optional[Dict]:
        """Build a contract transaction"""
        contract = self.get_contract(chain)
        if not contract:
            logger.error(f"No contract found for {chain}")
            return None
        
        try:
            function = getattr(contract.functions, function_name)
            return function(*args, **kwargs).build_transaction({
                'chainId': config.CHAINS[chain].chain_id,
                'gasPrice': self.get_web3(chain).eth.gas_price
            })
        except Exception as e:
            logger.error(f"Failed to build transaction for {function_name} on {chain}: {str(e)}")
            return None
    
    def get_events(self, chain: str, event_name: str, from_block: int, to_block: int = 'latest') -> list:
        """Get contract events"""
        contract = self.get_contract(chain)
        if not contract:
            return []
        
        try:
            event_filter = getattr(contract.events, event_name).create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            return event_filter.get_all_entries()
        except Exception as e:
            logger.error(f"Failed to get {event_name} events on {chain}: {str(e)}")
            return []
    
    def is_transaction_confirmed(self, chain: str, tx_hash: str) -> bool:
        """Check if transaction is confirmed"""
        receipt = self.get_transaction_receipt(chain, tx_hash)
        if not receipt:
            return False
        
        current_block = self.get_latest_block(chain)
        if not current_block:
            return False
        
        confirmations = current_block - receipt['blockNumber']
        required_confirmations = config.CHAINS[chain].confirmation_blocks
        
        return confirmations >= required_confirmations
    
    def get_native_balance(self, chain: str, address: str) -> Optional[int]:
        """Get native token balance (ETH/BNB)"""
        w3 = self.get_web3(chain)
        if not w3:
            return None
        
        try:
            return w3.eth.get_balance(address)
        except Exception as e:
            logger.error(f"Failed to get balance for {address} on {chain}: {str(e)}")
            return None
    
    def get_token_balance(self, chain: str, address: str) -> Optional[int]:
        """Get token balance from contract"""
        try:
            return self.call_contract_function(chain, 'balanceOf', address)
        except Exception as e:
            logger.error(f"Failed to get token balance for {address} on {chain}: {str(e)}")
            return None

# Global Web3 manager instance
web3_manager = Web3Manager()
