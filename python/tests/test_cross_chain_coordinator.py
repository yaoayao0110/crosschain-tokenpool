"""
Tests for CrossChainCoordinator
"""
import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from cross_chain_coordinator import CrossChainCoordinator, SwapStatus, CrossChainSwap
    from config import config
except ImportError:
    # If running from different directory
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
    from cross_chain_coordinator import CrossChainCoordinator, SwapStatus, CrossChainSwap
    from config import config

class TestCrossChainCoordinator:
    """Test cases for CrossChainCoordinator"""
    
    def setup_method(self):
        """Setup test environment"""
        self.coordinator = CrossChainCoordinator()
        
        # Mock web3_manager
        self.mock_web3_manager = Mock()
        
        # Sample addresses
        self.alice_address = "0x1234567890123456789012345678901234567890"
        self.bob_address = "0x0987654321098765432109876543210987654321"
        
        # Sample amounts (smaller values for testing)
        self.eth_amount = 100  # 100 tokens (within limits)
        self.token_amount = 500  # 500 tokens (within limits)
    
    def test_generate_secret(self):
        """Test secret generation"""
        secret, hash_lock = self.coordinator.generate_secret()
        
        # Check secret format
        assert len(secret) == config.CROSS_CHAIN.secret_length * 2  # hex string
        assert all(c in '0123456789abcdef' for c in secret.lower())
        
        # Check hash lock
        expected_hash = hashlib.sha256(bytes.fromhex(secret)).hexdigest()
        assert hash_lock == expected_hash
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_initiate_eth_to_bnb_swap_success(self, mock_web3_manager):
        """Test successful ETH to BNB swap initiation"""
        # Setup mocks
        mock_web3_manager.build_transaction.return_value = {'data': 'mock_tx_data'}
        mock_web3_manager.send_transaction.return_value = '0xmocktxhash'
        mock_web3_manager.wait_for_transaction.return_value = {
            'status': 1,
            'logs': [{'topics': ['0xmocktopic'], 'data': '0xmockdata'}]
        }
        
        # Mock swap ID extraction
        with patch.object(self.coordinator, '_extract_swap_id_from_receipt', return_value='0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'):
            swap = self.coordinator.initiate_eth_to_bnb_swap(
                sender=self.alice_address,
                recipient=self.bob_address,
                eth_amount=self.eth_amount
            )
        
        # Verify swap creation
        assert swap is not None
        assert swap.source_chain == 'ethereum'
        assert swap.target_chain == 'bsc'
        assert swap.sender == self.alice_address
        assert swap.recipient == self.bob_address
        assert swap.amount == self.eth_amount
        assert swap.status == SwapStatus.INITIATED
        
        # Verify swap is stored
        assert swap.swap_id in self.coordinator.active_swaps
        assert swap.swap_id in self.coordinator.swap_secrets
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_initiate_bnb_to_eth_swap_success(self, mock_web3_manager):
        """Test successful BNB to ETH swap initiation"""
        # Setup mocks
        mock_web3_manager.build_transaction.return_value = {'data': 'mock_tx_data'}
        mock_web3_manager.send_transaction.return_value = '0xmocktxhash'
        mock_web3_manager.wait_for_transaction.return_value = {
            'status': 1,
            'logs': [{'topics': ['0xmocktopic'], 'data': '0xmockdata'}]
        }
        
        # Mock swap ID extraction
        with patch.object(self.coordinator, '_extract_swap_id_from_receipt', return_value='0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'):
            swap = self.coordinator.initiate_bnb_to_eth_swap(
                sender=self.bob_address,
                recipient=self.alice_address,
                bnb_amount=self.eth_amount
            )
        
        # Verify swap creation
        assert swap is not None
        assert swap.source_chain == 'bsc'
        assert swap.target_chain == 'ethereum'
        assert swap.sender == self.bob_address
        assert swap.recipient == self.alice_address
        assert swap.amount == self.eth_amount
        assert swap.status == SwapStatus.INITIATED
    
    def test_validate_swap_params_valid(self):
        """Test swap parameter validation with valid inputs"""
        result = self.coordinator._validate_swap_params(
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=100
        )
        assert result is True
    
    def test_validate_swap_params_invalid_chain(self):
        """Test swap parameter validation with invalid chain"""
        result = self.coordinator._validate_swap_params(
            source_chain='invalid_chain',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=100
        )
        assert result is False
    
    def test_validate_swap_params_amount_too_small(self):
        """Test swap parameter validation with amount too small"""
        result = self.coordinator._validate_swap_params(
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=0
        )
        assert result is False
    
    def test_validate_swap_params_amount_too_large(self):
        """Test swap parameter validation with amount too large"""
        result = self.coordinator._validate_swap_params(
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=config.CROSS_CHAIN.max_swap_amount + 1
        )
        assert result is False
    
    def test_validate_swap_params_invalid_addresses(self):
        """Test swap parameter validation with invalid addresses"""
        result = self.coordinator._validate_swap_params(
            source_chain='ethereum',
            target_chain='bsc',
            sender='',
            recipient=self.bob_address,
            amount=100
        )
        assert result is False
        
        result = self.coordinator._validate_swap_params(
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient='',
            amount=100
        )
        assert result is False
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_complete_cross_chain_swap_success(self, mock_web3_manager):
        """Test successful cross-chain swap completion"""
        # Create a mock swap with proper hex values
        swap_id = '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        secret = '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890'
        
        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321',
            secret=secret,
            time_lock=1000,
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        # Add swap to coordinator
        self.coordinator.active_swaps[swap_id] = swap
        self.coordinator.swap_secrets[swap_id] = secret
        
        # Setup mocks
        mock_web3_manager.build_transaction.return_value = {'data': 'mock_tx_data'}
        mock_web3_manager.send_transaction.return_value = '0xmocktxhash'
        mock_web3_manager.wait_for_transaction.return_value = {'status': 1}
        
        # Complete swap
        result = self.coordinator.complete_cross_chain_swap(swap_id)
        
        # Verify completion
        assert result is True
        assert swap.status == SwapStatus.COMPLETED
        assert swap.target_tx_hash == '0xmocktxhash'
        
        # Verify transactions were called
        assert mock_web3_manager.build_transaction.call_count == 2  # source + target
        assert mock_web3_manager.send_transaction.call_count == 2
    
    def test_complete_cross_chain_swap_not_found(self):
        """Test completion of non-existent swap"""
        result = self.coordinator.complete_cross_chain_swap('non_existent_swap')
        assert result is False
    
    def test_complete_cross_chain_swap_wrong_status(self):
        """Test completion of swap with wrong status"""
        swap_id = 'mock_swap_id'
        
        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='mock_hash_lock',
            secret='mock_secret',
            time_lock=1000,
            status=SwapStatus.COMPLETED,  # Already completed
            created_at=1234567890
        )
        
        self.coordinator.active_swaps[swap_id] = swap
        
        result = self.coordinator.complete_cross_chain_swap(swap_id)
        assert result is False
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_refund_cross_chain_swap_success(self, mock_web3_manager):
        """Test successful cross-chain swap refund"""
        swap_id = '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'

        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321',
            secret='0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            time_lock=100,  # Low time lock for testing
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        self.coordinator.active_swaps[swap_id] = swap
        
        # Setup mocks
        mock_web3_manager.build_transaction.return_value = {'data': 'mock_tx_data'}
        mock_web3_manager.send_transaction.return_value = '0xmocktxhash'
        mock_web3_manager.wait_for_transaction.return_value = {'status': 1}
        mock_web3_manager.get_latest_block.return_value = 200  # Block > time_lock
        
        # Mock expiry check
        with patch.object(self.coordinator, '_is_swap_expired', return_value=True):
            result = self.coordinator.refund_cross_chain_swap(swap_id)
        
        # Verify refund
        assert result is True
        assert swap.status == SwapStatus.REFUNDED
    
    def test_refund_cross_chain_swap_not_expired(self):
        """Test refund of non-expired swap"""
        swap_id = 'mock_swap_id'
        
        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='mock_hash_lock',
            secret='mock_secret',
            time_lock=1000,
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        self.coordinator.active_swaps[swap_id] = swap
        
        # Mock expiry check
        with patch.object(self.coordinator, '_is_swap_expired', return_value=False):
            result = self.coordinator.refund_cross_chain_swap(swap_id)
        
        assert result is False
    
    def test_get_swap_status(self):
        """Test getting swap status"""
        swap_id = 'mock_swap_id'
        
        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='mock_hash_lock',
            secret='mock_secret',
            time_lock=1000,
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        self.coordinator.active_swaps[swap_id] = swap
        
        # Get existing swap
        result = self.coordinator.get_swap_status(swap_id)
        assert result == swap
        
        # Get non-existent swap
        result = self.coordinator.get_swap_status('non_existent')
        assert result is None
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_monitor_active_swaps(self, mock_web3_manager):
        """Test monitoring of active swaps"""
        swap_id = 'mock_swap_id'
        
        swap = CrossChainSwap(
            swap_id=swap_id,
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='mock_hash_lock',
            secret='mock_secret',
            time_lock=100,
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        self.coordinator.active_swaps[swap_id] = swap
        
        # Mock expiry check
        with patch.object(self.coordinator, '_is_swap_expired', return_value=True):
            self.coordinator.monitor_active_swaps()
        
        # Verify status update
        assert swap.status == SwapStatus.EXPIRED
    
    @patch('cross_chain_coordinator.web3_manager')
    def test_is_swap_expired(self, mock_web3_manager):
        """Test swap expiry check"""
        swap = CrossChainSwap(
            swap_id='mock_swap_id',
            source_chain='ethereum',
            target_chain='bsc',
            sender=self.alice_address,
            recipient=self.bob_address,
            amount=self.token_amount,
            hash_lock='mock_hash_lock',
            secret='mock_secret',
            time_lock=100,
            status=SwapStatus.INITIATED,
            created_at=1234567890
        )
        
        # Test not expired
        mock_web3_manager.get_latest_block.return_value = 50
        result = self.coordinator._is_swap_expired(swap)
        assert result is False
        
        # Test expired
        mock_web3_manager.get_latest_block.return_value = 150
        result = self.coordinator._is_swap_expired(swap)
        assert result is True
        
        # Test no block info
        mock_web3_manager.get_latest_block.return_value = None
        result = self.coordinator._is_swap_expired(swap)
        assert result is False

if __name__ == '__main__':
    pytest.main([__file__])
