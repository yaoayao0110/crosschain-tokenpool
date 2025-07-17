# 跨链代币池测试指南

本文档提供完整的测试步骤，从环境搭建到功能验证的详细说明。

## 📋 测试前准备

### 1. 环境要求
- Node.js 18+ 
- Python 3.9+
- Git

### 2. 项目初始化
```bash
# 克隆或进入项目目录
cd crosschain-tokenpool

# 安装Node.js依赖
npm install

# 安装Python依赖
cd python
pip install -r requirements.txt
cd ..
```

### 3. 环境配置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件（测试阶段可以使用默认值）
# 主要需要设置：
# PRIVATE_KEY=你的私钥（不带0x前缀）
# MANAGER_PRIVATE_KEY=管理者私钥
```

## 🧪 测试步骤

### 第一步：智能合约编译和测试

#### 1.1 编译合约
```bash
npx hardhat compile
```
**预期结果**: 
- 编译成功，无错误信息
- 生成 `artifacts/` 目录

#### 1.2 运行智能合约测试
```bash
npx hardhat test
```
**预期结果**:
```
CrossChainTokenPool
  Deployment
    ✓ Should set the correct initial parameters
    ✓ Should set the correct owner
  Native Token Swapping
    ✓ Should swap ETH for tokens correctly
    ✓ Should swap tokens for ETH correctly
    ✓ Should reject zero value swaps
  Cross-Chain HTLC
    ✓ Should initiate cross-chain swap correctly
    ✓ Should complete cross-chain swap with correct secret
    ✓ Should reject completion with wrong secret
    ✓ Should allow refund after time lock expires
    ✓ Should reject refund before time lock expires
  Manager Functions
    ✓ Should allow manager to mint tokens
    ✓ Should reject non-manager minting
    ✓ Should allow manager to update exchange rate
  Owner Functions
    ✓ Should allow owner to update manager
    ✓ Should allow owner to pause and unpause
    ✓ Should allow emergency withdraw

  15 passing
```

#### 1.3 运行演示脚本
```bash
npx hardhat run scripts/demo.js
```
**预期结果**:
```
=== Cross-Chain Token Pool Demo ===

Demo participants:
Owner: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Manager: 0x70997970C51812dc3A010C7d01b50e0d17dc79C8
Alice: 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
Bob: 0x90F79bf6EB2c4f870365E785982E1f101E93b906

1. Deploying contracts...
ETH Pool deployed to: 0x...
BSC Pool deployed to: 0x...

2. Demo: Basic Token Swapping
Alice swaps 1 ETH for tokens...
Alice's token balance: 100.0 CCETH

3. Demo: Cross-Chain HTLC Setup
Secret: 0x...
Hash Lock: 0x...

Alice initiates cross-chain swap (ETH → BSC)...
Swap ID: 0x...
Swap Amount: 500.0 tokens
Time Lock: Block 123
Current Block: 73

4. Demo: Cross-Chain Token Minting
Manager mints equivalent tokens for Bob on BSC side...
Bob's token balance on BSC: 500.0 CCBNB

5. Demo: Complete Cross-Chain Swap
Completing swap by revealing secret...
Cross-chain swap completed!
Alice's tokens burned on ETH side
Bob received tokens on BSC side

6. Demo: Bob swaps tokens for BNB
Bob's remaining token balance: 200.0 CCBNB
Bob successfully swapped tokens for BNB!

=== Final Balances ===
Alice's ETH tokens: 500.0 CCETH
Bob's BSC tokens: 200.0 CCBNB
ETH Pool native balance: 3.0 ETH
BSC Pool native balance: 1.7 BNB

=== Demo Completed Successfully! ===
```

### 第二步：Python后端测试

#### 2.1 运行Python单元测试
```bash
cd python
pytest tests/ -v
```
**预期结果**:
```
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_generate_secret PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_initiate_eth_to_bnb_swap_success PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_initiate_bnb_to_eth_swap_success PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_validate_swap_params_valid PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_validate_swap_params_invalid_chain PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_validate_swap_params_amount_too_small PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_validate_swap_params_amount_too_large PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_validate_swap_params_invalid_addresses PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_complete_cross_chain_swap_success PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_complete_cross_chain_swap_not_found PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_complete_cross_chain_swap_wrong_status PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_refund_cross_chain_swap_success PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_refund_cross_chain_swap_not_expired PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_get_swap_status PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_monitor_active_swaps PASSED
tests/test_cross_chain_coordinator.py::TestCrossChainCoordinator::test_is_swap_expired PASSED

========================= 16 passed =========================
```

#### 2.2 测试Python后端配置
```bash
cd python/src
python -c "from config import config; print('Config validation:', config.validate_config())"
```
**预期结果**:
```
Config validation: True
```
如果返回False，会显示具体的配置错误。

### 第三步：集成测试（本地网络）

#### 3.1 启动本地Hardhat网络
```bash
# 终端1：启动本地网络
npx hardhat node
```
**预期结果**:
```
Started HTTP and WebSocket JSON-RPC server at http://127.0.0.1:8545/

Accounts
========
Account #0: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 (10000 ETH)
Private Key: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
...
```

#### 3.2 部署合约到本地网络
```bash
# 终端2：部署合约
npx hardhat run scripts/deploy.js --network localhost
```
**预期结果**:
```
Starting CrossChainTokenPool deployment...
Deploying to network: localhost (Chain ID: 1337)
Deploying with account: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Account balance: 10000.0 ETH

Deployment parameters:
- Token Name: CrossChain Token (Local)
- Token Symbol: CCT-L
- Manager: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
- Exchange Rate: 100
- Default Time Lock: 10

Deploying CrossChainTokenPool...
CrossChainTokenPool deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
Waiting for confirmations...

Deployment verification:
- Name: CrossChain Token (Local)
- Symbol: CCT-L
- Manager: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
- Owner: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266

=== Testnet Setup ===
Performing testnet setup...
Setting deployer as manager...
Manager set to: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Adding initial liquidity...
Added 10.0 native tokens as liquidity
Received 1000.0 tokens
Testnet setup completed!

=== Deployment Summary ===
Network: localhost
Contract Address: 0x5FbDB2315678afecb367f032d93F642f64180aa3
Transaction Hash: 0x...
Gas Used: 2234567

=== Environment Variables ===
Add these to your .env file:
LOCAL_POOL_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
```

#### 3.3 更新环境配置
```bash
# 将部署的合约地址添加到.env文件
echo "ETH_POOL_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3" >> .env
echo "BSC_POOL_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3" >> .env
echo "ETH_RPC_URL=http://localhost:8545" >> .env
echo "BSC_RPC_URL=http://localhost:8545" >> .env
```

#### 3.4 启动Python后端
```bash
# 终端3：启动Python API服务
cd python/src
python app.py
```
**预期结果**:
```
2024-01-01 10:00:00,000 - __main__ - INFO - Starting Cross-Chain Token Pool API...
2024-01-01 10:00:00,001 - __main__ - INFO - Supported chains: ['ethereum', 'bsc']
2024-01-01 10:00:00,002 - web3_manager - INFO - Initialized ethereum connection successfully
2024-01-01 10:00:00,003 - web3_manager - INFO - Initialized bsc connection successfully
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://[::1]:5000
```

### 第四步：API功能测试

#### 4.1 健康检查
```bash
curl http://localhost:5000/health
```
**预期结果**:
```json
{
  "status": "healthy",
  "message": "Cross-chain token pool API is running"
}
```

#### 4.2 获取配置信息
```bash
curl http://localhost:5000/config
```
**预期结果**:
```json
{
  "chains": {
    "ethereum": {
      "name": "ethereum",
      "chain_id": 1,
      "native_symbol": "ETH",
      "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
      "block_time": 12
    },
    "bsc": {
      "name": "bsc", 
      "chain_id": 56,
      "native_symbol": "BNB",
      "contract_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
      "block_time": 3
    }
  },
  "cross_chain": {
    "default_time_lock_blocks": 100,
    "max_swap_amount": 1000,
    "min_swap_amount": 1
  }
}
```

#### 4.3 查询余额
```bash
curl "http://localhost:5000/balance/ethereum/0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
```
**预期结果**:
```json
{
  "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
  "chain": "ethereum",
  "native_balance": "9990000000000000000000",
  "token_balance": "1000000000000000000000",
  "native_symbol": "ETH"
}
```

#### 4.4 测试原生币换代币交易构建
```bash
curl -X POST http://localhost:5000/swap/native-to-token \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum",
    "amount": "1000000000000000000",
    "user_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
  }'
```
**预期结果**:
```json
{
  "transaction": {
    "to": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    "data": "0x...",
    "value": "1000000000000000000",
    "chainId": 1,
    "gasPrice": "20000000000"
  },
  "message": "Transaction built successfully. Sign and send this transaction."
}
```


