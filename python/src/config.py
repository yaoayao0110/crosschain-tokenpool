"""
Configuration module for cross-chain token pool
"""
import os
from dataclasses import dataclass
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ChainConfig:
    """Configuration for a blockchain network"""
    name: str
    rpc_url: str
    chain_id: int
    contract_address: str
    native_symbol: str
    block_time: int  # Average block time in seconds
    confirmation_blocks: int  # Required confirmations

@dataclass
class CrossChainConfig:
    """Cross-chain specific configuration"""
    default_time_lock_blocks: int
    manager_private_key: str
    manager_address: str
    secret_length: int = 32
    max_swap_amount: int = 1000  # Maximum swap amount in tokens
    min_swap_amount: int = 1     # Minimum swap amount in tokens

class Config:
    """Main configuration class"""
    
    # Flask configuration
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///crosschain.db')
    
    # Redis configuration for Celery
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Chain configurations
    CHAINS: Dict[str, ChainConfig] = {
        'ethereum': ChainConfig(
            name='ethereum',
            rpc_url=os.getenv('ETH_RPC_URL', 'http://localhost:8545'),
            chain_id=int(os.getenv('ETH_CHAIN_ID', '1')),
            contract_address=os.getenv('ETH_POOL_ADDRESS', ''),
            native_symbol='ETH',
            block_time=12,
            confirmation_blocks=3
        ),
        'bsc': ChainConfig(
            name='bsc',
            rpc_url=os.getenv('BSC_RPC_URL', 'https://bsc-dataseed1.binance.org/'),
            chain_id=int(os.getenv('BSC_CHAIN_ID', '56')),
            contract_address=os.getenv('BSC_POOL_ADDRESS', ''),
            native_symbol='BNB',
            block_time=3,
            confirmation_blocks=5
        )
    }
    
    # Cross-chain configuration
    CROSS_CHAIN = CrossChainConfig(
        default_time_lock_blocks=int(os.getenv('DEFAULT_TIME_LOCK_BLOCKS', '100')),
        manager_private_key=os.getenv('MANAGER_PRIVATE_KEY', ''),
        manager_address=os.getenv('MANAGER_ADDRESS', '')
    )
    
    # Contract ABI (key functions only - full ABI would be loaded from artifacts)
    CONTRACT_ABI = [
        {
            "inputs": [{"name": "hashLock", "type": "bytes32"}, {"name": "recipient", "type": "address"}, 
                      {"name": "amount", "type": "uint256"}, {"name": "timeLockBlocks", "type": "uint256"}],
            "name": "initiateCrossChain",
            "outputs": [{"name": "swapId", "type": "bytes32"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "swapId", "type": "bytes32"}, {"name": "secret", "type": "bytes32"}],
            "name": "completeCrossChain",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "swapId", "type": "bytes32"}],
            "name": "refundCrossChain",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
            "name": "mintForCrossChain",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "swapNativeForToken",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [{"name": "tokenAmount", "type": "uint256"}],
            "name": "swapTokenForNative",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "swapId", "type": "bytes32"}],
            "name": "getCrossChainSwap",
            "outputs": [
                {"name": "hashLock", "type": "bytes32"},
                {"name": "timeLock", "type": "uint256"},
                {"name": "sender", "type": "address"},
                {"name": "recipient", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "completed", "type": "bool"},
                {"name": "refunded", "type": "bool"},
                {"name": "createdAt", "type": "uint256"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "swapId", "type": "bytes32"},
                {"indexed": True, "name": "sender", "type": "address"},
                {"indexed": True, "name": "recipient", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"}
            ],
            "name": "CrossChainInitiated",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "swapId", "type": "bytes32"},
                {"indexed": False, "name": "secret", "type": "bytes32"}
            ],
            "name": "CrossChainCompleted",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "swapId", "type": "bytes32"}
            ],
            "name": "CrossChainRefunded",
            "type": "event"
        }
    ]
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration"""
        errors = []
        
        # Check chain configurations
        for chain_name, chain_config in cls.CHAINS.items():
            if not chain_config.contract_address:
                errors.append(f"Missing contract address for {chain_name}")
            if not chain_config.rpc_url:
                errors.append(f"Missing RPC URL for {chain_name}")
        
        # Check cross-chain configuration
        if not cls.CROSS_CHAIN.manager_private_key:
            errors.append("Missing manager private key")
        if not cls.CROSS_CHAIN.manager_address:
            errors.append("Missing manager address")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True

# Global config instance
config = Config()
