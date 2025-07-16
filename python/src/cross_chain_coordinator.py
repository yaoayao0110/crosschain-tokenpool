"""
Cross-chain coordinator for managing bidirectional ETH-BNB swaps
"""
import logging
import secrets
import hashlib
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import time
from threading import Lock

try:
    from .web3_manager import web3_manager
    from .config import config
except ImportError:
    from web3_manager import web3_manager
    from config import config

logger = logging.getLogger(__name__)

class SwapStatus(Enum):
    """Cross-chain swap status"""
    INITIATED = "initiated"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    EXPIRED = "expired"
    FAILED = "failed"

@dataclass
class CrossChainSwap:
    """Cross-chain swap data structure"""
    swap_id: str
    source_chain: str
    target_chain: str
    sender: str
    recipient: str
    amount: int
    hash_lock: str
    secret: Optional[str]
    time_lock: int
    status: SwapStatus
    created_at: int
    source_tx_hash: Optional[str] = None
    target_tx_hash: Optional[str] = None

class CrossChainCoordinator:
    """Coordinates cross-chain swaps between ETH and BSC"""
    
    def __init__(self):
        self.active_swaps: Dict[str, CrossChainSwap] = {}
        self.swap_secrets: Dict[str, str] = {}  # Store secrets for completed swaps
        self._lock = Lock()
    
    def generate_secret(self) -> Tuple[str, str]:
        """Generate a random secret and its hash"""
        secret = secrets.token_hex(config.CROSS_CHAIN.secret_length)
        hash_lock = hashlib.sha256(bytes.fromhex(secret)).hexdigest()
        return secret, hash_lock
    
    def initiate_eth_to_bnb_swap(
        self,
        sender: str,
        recipient: str,
        eth_amount: int,
        time_lock_blocks: Optional[int] = None
    ) -> Optional[CrossChainSwap]:
        """Initiate ETH to BNB cross-chain swap - Alice chooses secret and initiates first"""

        # Generate secret and hash lock
        secret, hash_lock = self.generate_secret()

        # Alice initiates on ETH chain first
        swap = self._initiate_cross_chain_swap(
            source_chain='ethereum',
            target_chain='bsc',
            sender=sender,
            recipient=recipient,
            amount=eth_amount,
            time_lock_blocks=time_lock_blocks,
            secret=secret,
            hash_lock=hash_lock
        )

        if swap:
            # Start monitoring for manager response
            self._start_monitoring_for_manager_response(swap)

        return swap
    
    def initiate_bnb_to_eth_swap(
        self, 
        sender: str, 
        recipient: str, 
        bnb_amount: int,
        time_lock_blocks: Optional[int] = None
    ) -> Optional[CrossChainSwap]:
        """Initiate BNB to ETH cross-chain swap"""
        return self._initiate_cross_chain_swap(
            source_chain='bsc',
            target_chain='ethereum',
            sender=sender,
            recipient=recipient,
            amount=bnb_amount,
            time_lock_blocks=time_lock_blocks
        )
    
    def _initiate_cross_chain_swap(
        self,
        source_chain: str,
        target_chain: str,
        sender: str,
        recipient: str,
        amount: int,
        time_lock_blocks: Optional[int] = None,
        secret: Optional[str] = None,
        hash_lock: Optional[str] = None
    ) -> Optional[CrossChainSwap]:
        """Internal method to initiate cross-chain swap"""
        
        # Validate inputs
        if not self._validate_swap_params(source_chain, target_chain, sender, recipient, amount):
            return None
        
        # Use provided secret and hash lock, or generate new ones
        if secret is None or hash_lock is None:
            secret, hash_lock = self.generate_secret()
        
        # Set time lock
        if time_lock_blocks is None:
            time_lock_blocks = config.CROSS_CHAIN.default_time_lock_blocks
        
        try:
            # Build transaction for source chain
            tx_data = web3_manager.build_transaction(
                source_chain,
                'initiateCrossChain',
                bytes.fromhex(hash_lock),
                recipient,
                amount,
                time_lock_blocks
            )
            
            if not tx_data:
                logger.error(f"Failed to build initiate transaction for {source_chain}")
                return None
            
            # Send transaction
            tx_hash = web3_manager.send_transaction(source_chain, tx_data)
            if not tx_hash:
                logger.error(f"Failed to send initiate transaction on {source_chain}")
                return None
            
            # Wait for transaction confirmation
            receipt = web3_manager.wait_for_transaction(source_chain, tx_hash)
            if not receipt or receipt['status'] != 1:
                logger.error(f"Initiate transaction failed on {source_chain}: {tx_hash}")
                return None
            
            # Extract swap ID from transaction logs
            swap_id = self._extract_swap_id_from_receipt(source_chain, receipt)
            if not swap_id:
                logger.error(f"Failed to extract swap ID from receipt")
                return None
            
            # Create swap object
            swap = CrossChainSwap(
                swap_id=swap_id,
                source_chain=source_chain,
                target_chain=target_chain,
                sender=sender,
                recipient=recipient,
                amount=amount,
                hash_lock=hash_lock,
                secret=secret,  # Store secret for later use
                time_lock=time_lock_blocks,
                status=SwapStatus.INITIATED,
                created_at=int(time.time()),
                source_tx_hash=tx_hash
            )
            
            # Store swap
            with self._lock:
                self.active_swaps[swap_id] = swap
                self.swap_secrets[swap_id] = secret
            
            logger.info(f"Cross-chain swap initiated: {swap_id} ({source_chain} -> {target_chain})")
            return swap
            
        except Exception as e:
            logger.error(f"Failed to initiate cross-chain swap: {str(e)}")
            return None
    
    def complete_cross_chain_swap(self, swap_id: str) -> bool:
        """Complete cross-chain swap by revealing secret and minting tokens"""
        
        with self._lock:
            swap = self.active_swaps.get(swap_id)
            if not swap:
                logger.error(f"Swap not found: {swap_id}")
                return False
            
            if swap.status != SwapStatus.INITIATED:
                logger.error(f"Swap {swap_id} is not in initiated status: {swap.status}")
                return False
            
            secret = self.swap_secrets.get(swap_id)
            if not secret:
                logger.error(f"Secret not found for swap: {swap_id}")
                return False
        
        try:
            # Step 1: Complete swap on source chain (burn tokens)
            # Remove 0x prefix if present
            swap_id_hex = swap_id[2:] if swap_id.startswith('0x') else swap_id
            secret_hex = secret[2:] if secret.startswith('0x') else secret

            source_tx_data = web3_manager.build_transaction(
                swap.source_chain,
                'completeCrossChain',
                bytes.fromhex(swap_id_hex),
                bytes.fromhex(secret_hex)
            )
            
            if source_tx_data:
                source_tx_hash = web3_manager.send_transaction(swap.source_chain, source_tx_data)
                if source_tx_hash:
                    source_receipt = web3_manager.wait_for_transaction(swap.source_chain, source_tx_hash)
                    if source_receipt and source_receipt['status'] == 1:
                        logger.info(f"Source chain completion successful: {source_tx_hash}")
                    else:
                        logger.error(f"Source chain completion failed: {source_tx_hash}")
                        return False
            
            # Step 2: Mint tokens on target chain
            target_tx_data = web3_manager.build_transaction(
                swap.target_chain,
                'mintForCrossChain',
                swap.recipient,
                swap.amount
            )
            
            if not target_tx_data:
                logger.error(f"Failed to build mint transaction for {swap.target_chain}")
                return False
            
            target_tx_hash = web3_manager.send_transaction(swap.target_chain, target_tx_data)
            if not target_tx_hash:
                logger.error(f"Failed to send mint transaction on {swap.target_chain}")
                return False
            
            target_receipt = web3_manager.wait_for_transaction(swap.target_chain, target_tx_hash)
            if not target_receipt or target_receipt['status'] != 1:
                logger.error(f"Mint transaction failed on {swap.target_chain}: {target_tx_hash}")
                return False
            
            # Update swap status
            with self._lock:
                swap.status = SwapStatus.COMPLETED
                swap.target_tx_hash = target_tx_hash
            
            logger.info(f"Cross-chain swap completed: {swap_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete cross-chain swap {swap_id}: {str(e)}")
            with self._lock:
                swap.status = SwapStatus.FAILED
            return False
    
    def refund_cross_chain_swap(self, swap_id: str) -> bool:
        """Refund cross-chain swap after timeout"""
        
        with self._lock:
            swap = self.active_swaps.get(swap_id)
            if not swap:
                logger.error(f"Swap not found: {swap_id}")
                return False
            
            if swap.status != SwapStatus.INITIATED:
                logger.error(f"Swap {swap_id} cannot be refunded, status: {swap.status}")
                return False
        
        try:
            # Check if swap is expired
            if not self._is_swap_expired(swap):
                logger.error(f"Swap {swap_id} is not yet expired")
                return False
            
            # Build refund transaction
            # Remove 0x prefix if present
            swap_id_hex = swap_id[2:] if swap_id.startswith('0x') else swap_id

            tx_data = web3_manager.build_transaction(
                swap.source_chain,
                'refundCrossChain',
                bytes.fromhex(swap_id_hex)
            )
            
            if not tx_data:
                logger.error(f"Failed to build refund transaction for {swap.source_chain}")
                return False
            
            # Send refund transaction
            tx_hash = web3_manager.send_transaction(swap.source_chain, tx_data)
            if not tx_hash:
                logger.error(f"Failed to send refund transaction on {swap.source_chain}")
                return False
            
            # Wait for confirmation
            receipt = web3_manager.wait_for_transaction(swap.source_chain, tx_hash)
            if not receipt or receipt['status'] != 1:
                logger.error(f"Refund transaction failed on {swap.source_chain}: {tx_hash}")
                return False
            
            # Update swap status
            with self._lock:
                swap.status = SwapStatus.REFUNDED
            
            logger.info(f"Cross-chain swap refunded: {swap_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refund cross-chain swap {swap_id}: {str(e)}")
            return False
    
    def get_swap_status(self, swap_id: str) -> Optional[CrossChainSwap]:
        """Get current status of a cross-chain swap"""
        with self._lock:
            return self.active_swaps.get(swap_id)
    
    def monitor_active_swaps(self):
        """Monitor active swaps and handle timeouts"""
        with self._lock:
            for swap_id, swap in self.active_swaps.items():
                if swap.status == SwapStatus.INITIATED:
                    if self._is_swap_expired(swap):
                        logger.warning(f"Swap {swap_id} has expired")
                        swap.status = SwapStatus.EXPIRED
    
    def _validate_swap_params(
        self, 
        source_chain: str, 
        target_chain: str, 
        sender: str, 
        recipient: str, 
        amount: int
    ) -> bool:
        """Validate swap parameters"""
        
        # Check supported chains
        if source_chain not in config.CHAINS or target_chain not in config.CHAINS:
            logger.error(f"Unsupported chain: {source_chain} or {target_chain}")
            return False
        
        # Check amount limits
        if amount < config.CROSS_CHAIN.min_swap_amount:
            logger.error(f"Amount too small: {amount}")
            return False
        
        if amount > config.CROSS_CHAIN.max_swap_amount:
            logger.error(f"Amount too large: {amount}")
            return False
        
        # Check addresses
        if not sender or not recipient:
            logger.error("Invalid sender or recipient address")
            return False
        
        return True
    
    def _extract_swap_id_from_receipt(self, chain: str, receipt: Dict) -> Optional[str]:
        """Extract swap ID from transaction receipt logs"""
        try:
            contract = web3_manager.get_contract(chain)
            if not contract:
                return None
            
            # Process logs to find CrossChainInitiated event
            for log in receipt['logs']:
                try:
                    decoded_log = contract.events.CrossChainInitiated().processLog(log)
                    return decoded_log['args']['swapId'].hex()
                except:
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Failed to extract swap ID: {str(e)}")
            return None
    
    def _is_swap_expired(self, swap: CrossChainSwap) -> bool:
        """Check if swap has expired"""
        current_block = web3_manager.get_latest_block(swap.source_chain)
        if not current_block:
            return False

        return current_block > swap.time_lock

    def _start_monitoring_for_manager_response(self, swap: CrossChainSwap):
        """Start monitoring for manager response to user's swap initiation"""
        logger.info(f"Started monitoring for manager response to swap {swap.swap_id}")
        # In a real implementation, this would start a background task
        # For demo purposes, we'll simulate immediate manager response

    def manager_respond_to_swap(
        self,
        hash_lock: str,
        recipient: str,
        amount: int,
        target_chain: str,
        time_lock_blocks: Optional[int] = None
    ) -> bool:
        """Manager responds to user's cross-chain swap by locking funds on target chain"""

        if time_lock_blocks is None:
            time_lock_blocks = config.CROSS_CHAIN.default_time_lock_blocks

        try:
            # Remove 0x prefix if present
            hash_lock_hex = hash_lock[2:] if hash_lock.startswith('0x') else hash_lock

            # Build transaction for manager response
            tx_data = web3_manager.build_transaction(
                target_chain,
                'managerRespondToCrossChain',
                bytes.fromhex(hash_lock_hex),
                recipient,
                amount,
                time_lock_blocks
            )

            if not tx_data:
                logger.error(f"Failed to build manager response transaction for {target_chain}")
                return False

            # Send transaction
            tx_hash = web3_manager.send_transaction(target_chain, tx_data)
            if not tx_hash:
                logger.error(f"Failed to send manager response transaction on {target_chain}")
                return False

            # Wait for transaction confirmation
            receipt = web3_manager.wait_for_transaction(target_chain, tx_hash)
            if not receipt or receipt['status'] != 1:
                logger.error(f"Manager response transaction failed on {target_chain}: {tx_hash}")
                return False

            logger.info(f"Manager successfully responded to swap on {target_chain}: {tx_hash}")
            return True

        except Exception as e:
            logger.error(f"Failed to send manager response: {str(e)}")
            return False

    def listen_for_cross_chain_initiations(self, chain: str, from_block: int = 'latest'):
        """Listen for cross-chain swap initiations to respond as manager"""
        try:
            events = web3_manager.get_events(chain, 'CrossChainInitiated', from_block)

            for event in events:
                hash_lock = event['args']['hashLock'].hex()
                sender = event['args']['sender']
                recipient = event['args']['recipient']
                amount = event['args']['amount']

                logger.info(f"Detected cross-chain initiation on {chain}:")
                logger.info(f"  Hash Lock: {hash_lock}")
                logger.info(f"  Sender: {sender}")
                logger.info(f"  Recipient: {recipient}")
                logger.info(f"  Amount: {amount}")

                # Determine target chain
                target_chain = 'bsc' if chain == 'ethereum' else 'ethereum'

                # Manager should respond by locking funds on target chain
                # In a real implementation, this would include validation logic
                logger.info(f"Manager should respond on {target_chain} for recipient {recipient}")

        except Exception as e:
            logger.error(f"Failed to listen for cross-chain initiations: {str(e)}")

    def listen_for_secret_reveals(self, chain: str, from_block: int = 'latest'):
        """Listen for secret reveals to automatically complete target chain"""
        try:
            events = web3_manager.get_events(chain, 'SecretRevealed', from_block)

            for event in events:
                hash_lock = event['args']['hashLock'].hex()
                secret = event['args']['secret'].hex()
                recipient = event['args']['recipient']
                amount = event['args']['amount']

                logger.info(f"Detected secret reveal on {chain}:")
                logger.info(f"  Hash Lock: {hash_lock}")
                logger.info(f"  Secret: {secret}")
                logger.info(f"  Recipient: {recipient}")
                logger.info(f"  Amount: {amount}")

                # Determine target chain
                target_chain = 'bsc' if chain == 'ethereum' else 'ethereum'

                # Automatically complete on target chain
                success = self.auto_complete_target_chain(
                    target_chain, hash_lock, secret, recipient, amount
                )

                if success:
                    logger.info(f"Successfully auto-completed swap on {target_chain}")
                else:
                    logger.error(f"Failed to auto-complete swap on {target_chain}")

        except Exception as e:
            logger.error(f"Failed to listen for secret reveals: {str(e)}")

    def auto_complete_target_chain(
        self,
        target_chain: str,
        hash_lock: str,
        secret: str,
        recipient: str,
        amount: int
    ) -> bool:
        """Automatically complete swap on target chain when secret is revealed"""
        try:
            # Remove 0x prefix if present
            hash_lock_hex = hash_lock[2:] if hash_lock.startswith('0x') else hash_lock
            secret_hex = secret[2:] if secret.startswith('0x') else secret

            # Build transaction for auto completion
            tx_data = web3_manager.build_transaction(
                target_chain,
                'autoCompleteManagerLock',
                bytes.fromhex(hash_lock_hex),
                bytes.fromhex(secret_hex),
                recipient,
                amount
            )

            if not tx_data:
                logger.error(f"Failed to build auto-completion transaction for {target_chain}")
                return False

            # Send transaction
            tx_hash = web3_manager.send_transaction(target_chain, tx_data)
            if not tx_hash:
                logger.error(f"Failed to send auto-completion transaction on {target_chain}")
                return False

            # Wait for transaction confirmation
            receipt = web3_manager.wait_for_transaction(target_chain, tx_hash)
            if not receipt or receipt['status'] != 1:
                logger.error(f"Auto-completion transaction failed on {target_chain}: {tx_hash}")
                return False

            logger.info(f"Auto-completion successful on {target_chain}: {tx_hash}")
            return True

        except Exception as e:
            logger.error(f"Failed to auto-complete target chain: {str(e)}")
            return False

    def start_atomic_monitoring(self):
        """Start monitoring for atomic cross-chain completion"""
        logger.info("Starting atomic cross-chain monitoring...")

        # In a real implementation, this would run in background threads
        # For demo purposes, we'll simulate the monitoring

        # Monitor both chains for secret reveals
        self.listen_for_secret_reveals('ethereum')
        self.listen_for_secret_reveals('bsc')

# Global coordinator instance
cross_chain_coordinator = CrossChainCoordinator()
