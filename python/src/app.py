"""
Flask API for cross-chain token pool
"""
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

try:
    from .config import config
    from .cross_chain_coordinator import cross_chain_coordinator, SwapStatus
    from .web3_manager import web3_manager
except ImportError:
    from config import config
    from cross_chain_coordinator import cross_chain_coordinator, SwapStatus
    from web3_manager import web3_manager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)

# Configure Flask
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.FLASK_DEBUG

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Cross-chain token pool API is running'
    })

@app.route('/config', methods=['GET'])
def get_config():
    """Get public configuration"""
    return jsonify({
        'chains': {
            name: {
                'name': chain_config.name,
                'chain_id': chain_config.chain_id,
                'native_symbol': chain_config.native_symbol,
                'contract_address': chain_config.contract_address,
                'block_time': chain_config.block_time
            }
            for name, chain_config in config.CHAINS.items()
        },
        'cross_chain': {
            'default_time_lock_blocks': config.CROSS_CHAIN.default_time_lock_blocks,
            'max_swap_amount': config.CROSS_CHAIN.max_swap_amount,
            'min_swap_amount': config.CROSS_CHAIN.min_swap_amount
        }
    })

@app.route('/balance/<chain>/<address>', methods=['GET'])
def get_balance(chain, address):
    """Get native and token balance for an address"""
    try:
        if chain not in config.CHAINS:
            return jsonify({'error': 'Unsupported chain'}), 400
        
        # Get native balance
        native_balance = web3_manager.get_native_balance(chain, address)
        
        # Get token balance
        token_balance = web3_manager.get_token_balance(chain, address)
        
        return jsonify({
            'address': address,
            'chain': chain,
            'native_balance': str(native_balance) if native_balance is not None else None,
            'token_balance': str(token_balance) if token_balance is not None else None,
            'native_symbol': config.CHAINS[chain].native_symbol
        })
        
    except Exception as e:
        logger.error(f"Failed to get balance: {str(e)}")
        return jsonify({'error': 'Failed to get balance'}), 500

@app.route('/swap/native-to-token', methods=['POST'])
def swap_native_to_token():
    """Swap native coin for tokens"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['chain', 'amount', 'user_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        chain = data['chain']
        amount = int(data['amount'])
        user_address = data['user_address']
        
        if chain not in config.CHAINS:
            return jsonify({'error': 'Unsupported chain'}), 400
        
        # Build transaction
        tx_data = web3_manager.build_transaction(
            chain,
            'swapNativeForToken'
        )
        
        if not tx_data:
            return jsonify({'error': 'Failed to build transaction'}), 500
        
        # Add value to transaction
        tx_data['value'] = amount
        tx_data['to'] = config.CHAINS[chain].contract_address
        
        return jsonify({
            'transaction': tx_data,
            'message': 'Transaction built successfully. Sign and send this transaction.'
        })
        
    except Exception as e:
        logger.error(f"Failed to build swap transaction: {str(e)}")
        return jsonify({'error': 'Failed to build transaction'}), 500

@app.route('/swap/token-to-native', methods=['POST'])
def swap_token_to_native():
    """Swap tokens for native coin"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['chain', 'amount', 'user_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        chain = data['chain']
        amount = int(data['amount'])
        user_address = data['user_address']
        
        if chain not in config.CHAINS:
            return jsonify({'error': 'Unsupported chain'}), 400
        
        # Build transaction
        tx_data = web3_manager.build_transaction(
            chain,
            'swapTokenForNative',
            amount
        )
        
        if not tx_data:
            return jsonify({'error': 'Failed to build transaction'}), 500
        
        return jsonify({
            'transaction': tx_data,
            'message': 'Transaction built successfully. Sign and send this transaction.'
        })
        
    except Exception as e:
        logger.error(f"Failed to build swap transaction: {str(e)}")
        return jsonify({'error': 'Failed to build transaction'}), 500

@app.route('/cross-chain/initiate', methods=['POST'])
def initiate_cross_chain():
    """Initiate cross-chain swap"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['source_chain', 'target_chain', 'sender', 'recipient', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        source_chain = data['source_chain']
        target_chain = data['target_chain']
        sender = data['sender']
        recipient = data['recipient']
        amount = int(data['amount'])
        time_lock_blocks = data.get('time_lock_blocks')
        
        # Validate chains
        if source_chain not in config.CHAINS or target_chain not in config.CHAINS:
            return jsonify({'error': 'Unsupported chain'}), 400
        
        # Initiate swap based on direction
        if source_chain == 'ethereum' and target_chain == 'bsc':
            swap = cross_chain_coordinator.initiate_eth_to_bnb_swap(
                sender, recipient, amount, time_lock_blocks
            )
        elif source_chain == 'bsc' and target_chain == 'ethereum':
            swap = cross_chain_coordinator.initiate_bnb_to_eth_swap(
                sender, recipient, amount, time_lock_blocks
            )
        else:
            return jsonify({'error': 'Unsupported swap direction'}), 400
        
        if not swap:
            return jsonify({'error': 'Failed to initiate cross-chain swap'}), 500
        
        return jsonify({
            'swap_id': swap.swap_id,
            'status': swap.status.value,
            'source_chain': swap.source_chain,
            'target_chain': swap.target_chain,
            'amount': str(swap.amount),
            'hash_lock': swap.hash_lock,
            'time_lock': swap.time_lock,
            'source_tx_hash': swap.source_tx_hash,
            'message': 'Cross-chain swap initiated successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to initiate cross-chain swap: {str(e)}")
        return jsonify({'error': 'Failed to initiate swap'}), 500

@app.route('/cross-chain/complete/<swap_id>', methods=['POST'])
def complete_cross_chain(swap_id):
    """Complete cross-chain swap"""
    try:
        success = cross_chain_coordinator.complete_cross_chain_swap(swap_id)
        
        if success:
            swap = cross_chain_coordinator.get_swap_status(swap_id)
            return jsonify({
                'swap_id': swap_id,
                'status': swap.status.value if swap else 'unknown',
                'target_tx_hash': swap.target_tx_hash if swap else None,
                'message': 'Cross-chain swap completed successfully'
            })
        else:
            return jsonify({'error': 'Failed to complete cross-chain swap'}), 500
            
    except Exception as e:
        logger.error(f"Failed to complete cross-chain swap: {str(e)}")
        return jsonify({'error': 'Failed to complete swap'}), 500

@app.route('/cross-chain/refund/<swap_id>', methods=['POST'])
def refund_cross_chain(swap_id):
    """Refund cross-chain swap"""
    try:
        success = cross_chain_coordinator.refund_cross_chain_swap(swap_id)
        
        if success:
            swap = cross_chain_coordinator.get_swap_status(swap_id)
            return jsonify({
                'swap_id': swap_id,
                'status': swap.status.value if swap else 'unknown',
                'message': 'Cross-chain swap refunded successfully'
            })
        else:
            return jsonify({'error': 'Failed to refund cross-chain swap'}), 500
            
    except Exception as e:
        logger.error(f"Failed to refund cross-chain swap: {str(e)}")
        return jsonify({'error': 'Failed to refund swap'}), 500

@app.route('/cross-chain/status/<swap_id>', methods=['GET'])
def get_cross_chain_status(swap_id):
    """Get cross-chain swap status"""
    try:
        swap = cross_chain_coordinator.get_swap_status(swap_id)
        
        if not swap:
            return jsonify({'error': 'Swap not found'}), 404
        
        return jsonify({
            'swap_id': swap.swap_id,
            'status': swap.status.value,
            'source_chain': swap.source_chain,
            'target_chain': swap.target_chain,
            'sender': swap.sender,
            'recipient': swap.recipient,
            'amount': str(swap.amount),
            'hash_lock': swap.hash_lock,
            'time_lock': swap.time_lock,
            'created_at': swap.created_at,
            'source_tx_hash': swap.source_tx_hash,
            'target_tx_hash': swap.target_tx_hash
        })
        
    except Exception as e:
        logger.error(f"Failed to get swap status: {str(e)}")
        return jsonify({'error': 'Failed to get swap status'}), 500

@app.route('/cross-chain/active', methods=['GET'])
def get_active_swaps():
    """Get all active cross-chain swaps"""
    try:
        active_swaps = []
        
        for swap_id, swap in cross_chain_coordinator.active_swaps.items():
            active_swaps.append({
                'swap_id': swap.swap_id,
                'status': swap.status.value,
                'source_chain': swap.source_chain,
                'target_chain': swap.target_chain,
                'sender': swap.sender,
                'recipient': swap.recipient,
                'amount': str(swap.amount),
                'created_at': swap.created_at
            })
        
        return jsonify({
            'active_swaps': active_swaps,
            'count': len(active_swaps)
        })
        
    except Exception as e:
        logger.error(f"Failed to get active swaps: {str(e)}")
        return jsonify({'error': 'Failed to get active swaps'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ===== 管理者功能接口 =====

@app.route('/admin/exchange-rate/<chain>', methods=['GET'])
def get_exchange_rate(chain):
    """获取指定链的当前汇率"""
    try:
        if chain not in config.CHAINS:
            return jsonify({'error': f'Unsupported chain: {chain}'}), 400

        # 获取当前汇率
        rate = web3_manager.call_contract_function(chain, 'exchangeRate')
        if rate is None:
            return jsonify({'error': 'Failed to get exchange rate'}), 500

        return jsonify({
            'chain': chain,
            'exchange_rate': str(rate),
            'exchange_rate_formatted': f"1 {config.CHAINS[chain].native_symbol} = {rate} tokens",
            'native_symbol': config.CHAINS[chain].native_symbol
        })
    except Exception as e:
        logger.error(f"Failed to get exchange rate for {chain}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/exchange-rate/<chain>', methods=['POST'])
def set_exchange_rate(chain):
    """设置指定链的汇率（仅管理者）"""
    try:
        if chain not in config.CHAINS:
            return jsonify({'error': f'Unsupported chain: {chain}'}), 400

        data = request.get_json()
        if not data or 'new_rate' not in data:
            return jsonify({'error': 'Missing new_rate parameter'}), 400

        new_rate = data['new_rate']

        # 验证汇率
        try:
            new_rate_wei = int(new_rate)
            if new_rate_wei <= 0:
                return jsonify({'error': 'Exchange rate must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid exchange rate format'}), 400

        # 获取当前汇率
        old_rate = web3_manager.call_contract_function(chain, 'exchangeRate')

        # 构建交易
        tx_data = web3_manager.build_transaction(chain, 'setExchangeRate', new_rate_wei)
        if not tx_data:
            return jsonify({'error': 'Failed to build transaction'}), 500

        # 发送交易
        tx_hash = web3_manager.send_transaction(chain, tx_data)
        if not tx_hash:
            return jsonify({'error': 'Failed to send transaction'}), 500

        # 等待交易确认
        receipt = web3_manager.wait_for_transaction(chain, tx_hash)
        if not receipt or receipt['status'] != 1:
            return jsonify({'error': f'Transaction failed: {tx_hash}'}), 500

        return jsonify({
            'success': True,
            'chain': chain,
            'old_rate': str(old_rate),
            'new_rate': str(new_rate_wei),
            'old_rate_formatted': f"1 {config.CHAINS[chain].native_symbol} = {old_rate} tokens",
            'new_rate_formatted': f"1 {config.CHAINS[chain].native_symbol} = {new_rate_wei} tokens",
            'transaction_hash': tx_hash,
            'block_number': receipt['blockNumber']
        })

    except Exception as e:
        logger.error(f"Failed to set exchange rate for {chain}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/pool-info/<chain>', methods=['GET'])
def get_pool_info(chain):
    """获取代币池的详细信息"""
    try:
        if chain not in config.CHAINS:
            return jsonify({'error': f'Unsupported chain: {chain}'}), 400

        # 获取合约信息
        name = web3_manager.call_contract_function(chain, 'name')
        symbol = web3_manager.call_contract_function(chain, 'symbol')
        total_supply = web3_manager.call_contract_function(chain, 'totalSupply')
        exchange_rate = web3_manager.call_contract_function(chain, 'exchangeRate')
        manager = web3_manager.call_contract_function(chain, 'manager')
        owner = web3_manager.call_contract_function(chain, 'owner')
        paused = web3_manager.call_contract_function(chain, 'paused')

        # 获取合约原生币余额
        contract_address = config.CHAINS[chain].contract_address
        native_balance = web3_manager.get_native_balance(chain, contract_address)

        return jsonify({
            'chain': chain,
            'contract_address': contract_address,
            'token_info': {
                'name': name,
                'symbol': symbol,
                'total_supply': str(total_supply),
                'total_supply_formatted': f"{total_supply / 10**18:.2f} {symbol}"
            },
            'exchange_rate': {
                'rate': str(exchange_rate),
                'formatted': f"1 {config.CHAINS[chain].native_symbol} = {exchange_rate} {symbol}"
            },
            'balances': {
                'native_balance': str(native_balance),
                'native_balance_formatted': f"{native_balance / 10**18:.4f} {config.CHAINS[chain].native_symbol}"
            },
            'management': {
                'owner': owner,
                'manager': manager,
                'paused': paused
            }
        })

    except Exception as e:
        logger.error(f"Failed to get pool info for {chain}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/account-info/<chain>/<address>', methods=['GET'])
def get_account_info(chain, address):
    """获取账户的详细余额信息"""
    try:
        if chain not in config.CHAINS:
            return jsonify({'error': f'Unsupported chain: {chain}'}), 400

        # 获取原生币余额
        native_balance = web3_manager.get_native_balance(chain, address)

        # 获取代币余额
        token_balance = web3_manager.call_contract_function(chain, 'balanceOf', address)

        # 获取代币信息
        symbol = web3_manager.call_contract_function(chain, 'symbol')

        return jsonify({
            'chain': chain,
            'address': address,
            'balances': {
                'native': {
                    'balance': str(native_balance),
                    'formatted': f"{native_balance / 10**18:.4f} {config.CHAINS[chain].native_symbol}",
                    'symbol': config.CHAINS[chain].native_symbol
                },
                'token': {
                    'balance': str(token_balance),
                    'formatted': f"{token_balance / 10**18:.4f} {symbol}",
                    'symbol': symbol
                }
            }
        })

    except Exception as e:
        logger.error(f"Failed to get account info for {chain}/{address}: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Validate configuration
    if not config.validate_config():
        logger.error("Configuration validation failed")
        exit(1)
    
    logger.info("Starting Cross-Chain Token Pool API...")
    logger.info(f"Supported chains: {list(config.CHAINS.keys())}")
    
    # Start monitoring active swaps in background
    # In production, this should be done with Celery or similar
    import threading
    def monitor_swaps():
        import time
        while True:
            try:
                cross_chain_coordinator.monitor_active_swaps()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error monitoring swaps: {str(e)}")
                time.sleep(60)  # Wait longer on error
    
    monitor_thread = threading.Thread(target=monitor_swaps, daemon=True)
    monitor_thread.start()
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=config.FLASK_DEBUG
    )
