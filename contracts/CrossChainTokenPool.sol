// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

/**
 * @title CrossChainTokenPool
 * @dev Unified cross-chain token pool contract supporting bidirectional swapping
 * Supports ETH<->Token and BNB<->Token with HTLC cross-chain mechanism
 */
contract CrossChainTokenPool is ERC20, Ownable, ReentrancyGuard, Pausable {
    
    // Cross-chain swap structure for HTLC
    struct CrossChainSwap {
        bytes32 hashLock;      // Hash lock (hash of secret)
        uint256 timeLock;      // Time lock (block number)
        address sender;        // Sender address
        address recipient;     // Recipient address on target chain
        uint256 amount;        // Locked token amount
        bool completed;        // Whether completed
        bool refunded;         // Whether refunded
        uint256 createdAt;     // Creation block number
        bool isManagerLocked;  // Whether manager has locked funds for this swap
    }

    // Manager locked funds for cross-chain swaps
    struct ManagerLock {
        bytes32 hashLock;      // Hash lock (same as user swap)
        uint256 timeLock;      // Time lock (block number)
        address recipient;     // Who will receive the tokens
        uint256 amount;        // Locked token amount
        bool completed;        // Whether completed
        bool refunded;         // Whether refunded
        uint256 createdAt;     // Creation block number
    }
    
    // State variables
    address public manager;                                    // Cross-chain manager
    uint256 public exchangeRate;                              // Native coin to token rate (1 ETH/BNB = exchangeRate tokens)
    uint256 public constant RATE_PRECISION = 1e18;           // Rate precision
    uint256 public defaultTimeLock;                           // Default time lock blocks
    
    // Cross-chain swaps mapping
    mapping(bytes32 => CrossChainSwap) public crossChainSwaps;

    // Manager locked funds mapping
    mapping(bytes32 => ManagerLock) public managerLocks;
    
    // Events
    event NativeSwappedForToken(address indexed user, uint256 nativeAmount, uint256 tokenAmount);
    event TokenSwappedForNative(address indexed user, uint256 tokenAmount, uint256 nativeAmount);
    event CrossChainInitiated(
        bytes32 indexed swapId,
        bytes32 indexed hashLock,
        address indexed sender,
        address recipient,
        uint256 amount,
        uint256 timeLock
    );
    event CrossChainCompleted(bytes32 indexed swapId, bytes32 secret);
    event CrossChainRefunded(bytes32 indexed swapId);
    event ManagerLockCreated(bytes32 indexed hashLock, address indexed recipient, uint256 amount);
    event ManagerLockCompleted(bytes32 indexed hashLock, bytes32 secret);
    event ManagerLockRefunded(bytes32 indexed hashLock);
    event SecretRevealed(bytes32 indexed hashLock, bytes32 secret, address indexed recipient, uint256 amount);
    event ExchangeRateUpdated(uint256 oldRate, uint256 newRate);
    event ManagerUpdated(address oldManager, address newManager);
    
    // Modifiers
    modifier onlyManager() {
        require(msg.sender == manager, "Only manager can call this function");
        _;
    }
    
    modifier validSwap(bytes32 swapId) {
        require(crossChainSwaps[swapId].sender != address(0), "Swap does not exist");
        require(!crossChainSwaps[swapId].completed, "Swap already completed");
        require(!crossChainSwaps[swapId].refunded, "Swap already refunded");
        _;
    }
    
    constructor(
        string memory name,
        string memory symbol,
        address _manager,
        uint256 _exchangeRate,
        uint256 _defaultTimeLock
    ) ERC20(name, symbol) {
        require(_manager != address(0), "Manager cannot be zero address");
        require(_exchangeRate > 0, "Exchange rate must be positive");
        require(_defaultTimeLock > 0, "Time lock must be positive");
        
        manager = _manager;
        exchangeRate = _exchangeRate;
        defaultTimeLock = _defaultTimeLock;
    }
    
    /**
     * @dev Swap native coin (ETH/BNB) for tokens
     */
    function swapNativeForToken() external payable nonReentrant whenNotPaused {
        require(msg.value > 0, "Must send native coin");
        
        uint256 tokenAmount = (msg.value * exchangeRate) / RATE_PRECISION;
        require(tokenAmount > 0, "Token amount must be positive");
        
        _mint(msg.sender, tokenAmount);
        
        emit NativeSwappedForToken(msg.sender, msg.value, tokenAmount);
    }
    
    /**
     * @dev Swap tokens for native coin (ETH/BNB)
     */
    function swapTokenForNative(uint256 tokenAmount) external nonReentrant whenNotPaused {
        require(tokenAmount > 0, "Token amount must be positive");
        require(balanceOf(msg.sender) >= tokenAmount, "Insufficient token balance");
        
        uint256 nativeAmount = (tokenAmount * RATE_PRECISION) / exchangeRate;
        require(address(this).balance >= nativeAmount, "Insufficient native coin in pool");
        
        _burn(msg.sender, tokenAmount);
        payable(msg.sender).transfer(nativeAmount);
        
        emit TokenSwappedForNative(msg.sender, tokenAmount, nativeAmount);
    }
    
    /**
     * @dev Initiate cross-chain swap with HTLC
     * Alice chooses secret and initiates the swap first
     */
    function initiateCrossChain(
        bytes32 hashLock,
        address recipient,
        uint256 amount,
        uint256 timeLockBlocks
    ) external nonReentrant whenNotPaused returns (bytes32 swapId) {
        require(hashLock != bytes32(0), "Hash lock cannot be empty");
        require(recipient != address(0), "Recipient cannot be zero address");
        require(amount > 0, "Amount must be positive");
        require(balanceOf(msg.sender) >= amount, "Insufficient token balance");
        require(timeLockBlocks > 0, "Time lock must be positive");

        swapId = keccak256(abi.encodePacked(
            hashLock,
            msg.sender,
            recipient,
            amount,
            block.number,
            block.timestamp
        ));

        require(crossChainSwaps[swapId].sender == address(0), "Swap ID already exists");

        // Lock tokens
        _transfer(msg.sender, address(this), amount);

        // Create cross-chain swap
        crossChainSwaps[swapId] = CrossChainSwap({
            hashLock: hashLock,
            timeLock: block.number + timeLockBlocks,
            sender: msg.sender,
            recipient: recipient,
            amount: amount,
            completed: false,
            refunded: false,
            createdAt: block.number,
            isManagerLocked: false  // Will be set to true when manager responds
        });

        emit CrossChainInitiated(swapId, hashLock, msg.sender, recipient, amount, block.number + timeLockBlocks);
    }
    
    /**
     * @dev Complete cross-chain swap by revealing secret (burns tokens on this chain)
     * This function also triggers automatic completion on target chain if possible
     */
    function completeCrossChain(bytes32 swapId, bytes32 secret)
        external
        validSwap(swapId)
        nonReentrant
        whenNotPaused
    {
        CrossChainSwap storage swap = crossChainSwaps[swapId];
        require(block.number <= swap.timeLock, "Time lock expired");
        require(keccak256(abi.encodePacked(secret)) == swap.hashLock, "Invalid secret");

        swap.completed = true;

        // Burn the locked tokens (corresponding tokens will be released on target chain)
        _burn(address(this), swap.amount);

        // Emit event with secret for automatic target chain completion
        emit CrossChainCompleted(swapId, secret);

        // Also emit a special event for cross-chain automation
        emit SecretRevealed(swap.hashLock, secret, swap.recipient, swap.amount);
    }

    /**
     * @dev Verify and link cross-chain swap with manager lock
     */
    function linkCrossChainSwap(bytes32 swapId, bytes32 hashLock)
        external
        onlyManager
        whenNotPaused
    {
        CrossChainSwap storage swap = crossChainSwaps[swapId];
        require(swap.sender != address(0), "Swap does not exist");
        require(swap.hashLock == hashLock, "Hash lock mismatch");
        require(!swap.isManagerLocked, "Swap already linked");

        ManagerLock storage lock = managerLocks[hashLock];
        require(lock.recipient != address(0), "Manager lock does not exist");
        require(lock.recipient == swap.recipient, "Recipient mismatch");
        require(lock.amount == swap.amount, "Amount mismatch");

        swap.isManagerLocked = true;
    }

    /**
     * @dev Complete both sides of cross-chain swap atomically (anyone can call)
     * This function can be called on either chain to complete both sides
     */
    function completeAtomicSwap(bytes32 swapId, bytes32 secret)
        external
        nonReentrant
        whenNotPaused
    {
        // Complete user swap (burn tokens)
        CrossChainSwap storage swap = crossChainSwaps[swapId];
        if (swap.sender != address(0) && !swap.completed && !swap.refunded) {
            require(block.number <= swap.timeLock, "User swap time lock expired");
            require(keccak256(abi.encodePacked(secret)) == swap.hashLock, "Invalid secret");

            swap.completed = true;
            _burn(address(this), swap.amount);
            emit CrossChainCompleted(swapId, secret);
        }

        // Complete manager lock (release tokens to recipient)
        ManagerLock storage lock = managerLocks[swap.hashLock];
        if (lock.recipient != address(0) && !lock.completed && !lock.refunded) {
            require(block.number <= lock.timeLock, "Manager lock time lock expired");
            require(keccak256(abi.encodePacked(secret)) == lock.hashLock, "Invalid secret");

            lock.completed = true;
            _transfer(address(this), lock.recipient, lock.amount);
            emit ManagerLockCompleted(lock.hashLock, secret);
        }
    }
    
    /**
     * @dev Refund cross-chain swap after time lock expires
     */
    function refundCrossChain(bytes32 swapId) 
        external 
        validSwap(swapId) 
        nonReentrant 
        whenNotPaused 
    {
        CrossChainSwap storage swap = crossChainSwaps[swapId];
        require(block.number > swap.timeLock, "Time lock not expired");
        require(msg.sender == swap.sender, "Only sender can refund");
        
        swap.refunded = true;
        
        // Return locked tokens to sender
        _transfer(address(this), swap.sender, swap.amount);
        
        emit CrossChainRefunded(swapId);
    }
    
    /**
     * @dev Manager responds to cross-chain transfer by preparing tokens on target chain
     * This represents the target chain side of a cross-chain token transfer
     * Tokens are pre-minted and locked, will be released when source chain burn is confirmed
     */
    function managerRespondToCrossChain(
        bytes32 hashLock,
        address recipient,
        uint256 amount,
        uint256 timeLockBlocks
    ) external onlyManager whenNotPaused {
        require(hashLock != bytes32(0), "Hash lock cannot be empty");
        require(recipient != address(0), "Recipient cannot be zero address");
        require(amount > 0, "Amount must be positive");
        require(timeLockBlocks > 0, "Time lock must be positive");
        require(managerLocks[hashLock].recipient == address(0), "Hash lock already used");

        // Pre-mint tokens for the cross-chain transfer
        // These tokens will be released to recipient when source chain burn is confirmed
        // This maintains the total supply balance across all chains
        _mint(address(this), amount);

        // Create manager lock with shorter time lock (manager should complete before user's expires)
        managerLocks[hashLock] = ManagerLock({
            hashLock: hashLock,
            timeLock: block.number + timeLockBlocks,
            recipient: recipient,
            amount: amount,
            completed: false,
            refunded: false,
            createdAt: block.number
        });

        emit ManagerLockCreated(hashLock, recipient, amount);
    }

    /**
     * @dev Complete manager lock by revealing secret (anyone can call)
     */
    function completeManagerLock(bytes32 hashLock, bytes32 secret)
        external
        nonReentrant
        whenNotPaused
    {
        ManagerLock storage lock = managerLocks[hashLock];
        require(lock.recipient != address(0), "Manager lock does not exist");
        require(!lock.completed, "Manager lock already completed");
        require(!lock.refunded, "Manager lock already refunded");
        require(block.number <= lock.timeLock, "Time lock expired");
        require(keccak256(abi.encodePacked(secret)) == lock.hashLock, "Invalid secret");

        lock.completed = true;

        // Transfer locked tokens to recipient
        _transfer(address(this), lock.recipient, lock.amount);

        emit ManagerLockCompleted(hashLock, secret);
    }

    /**
     * @dev Auto-complete manager lock when secret is revealed on source chain
     * This function is called by automation when SecretRevealed event is detected
     * Transfers the minted tokens to the recipient (Bob)
     */
    function autoCompleteManagerLock(bytes32 hashLock, bytes32 secret, address recipient, uint256 amount)
        external
        onlyManager
        nonReentrant
        whenNotPaused
    {
        ManagerLock storage lock = managerLocks[hashLock];
        require(lock.recipient != address(0), "Manager lock does not exist");
        require(!lock.completed, "Manager lock already completed");
        require(!lock.refunded, "Manager lock already refunded");
        require(block.number <= lock.timeLock, "Time lock expired");
        require(keccak256(abi.encodePacked(secret)) == lock.hashLock, "Invalid secret");
        require(lock.recipient == recipient, "Recipient mismatch");
        require(lock.amount == amount, "Amount mismatch");

        lock.completed = true;

        // Transfer the minted tokens to recipient (Bob)
        // These tokens were minted when manager responded to Alice's swap
        _transfer(address(this), lock.recipient, lock.amount);

        emit ManagerLockCompleted(hashLock, secret);
    }

    /**
     * @dev Refund manager lock after time lock expires
     * Burns the minted tokens since the cross-chain swap failed
     */
    function refundManagerLock(bytes32 hashLock)
        external
        onlyManager
        nonReentrant
        whenNotPaused
    {
        ManagerLock storage lock = managerLocks[hashLock];
        require(lock.recipient != address(0), "Manager lock does not exist");
        require(!lock.completed, "Manager lock already completed");
        require(!lock.refunded, "Manager lock already refunded");
        require(block.number > lock.timeLock, "Time lock not expired");

        lock.refunded = true;

        // Burn the locked tokens since the cross-chain swap failed
        // This maintains the token supply balance across chains
        _burn(address(this), lock.amount);

        emit ManagerLockRefunded(hashLock);
    }
    
    /**
     * @dev Update exchange rate (only manager)
     */
    function setExchangeRate(uint256 newRate) external onlyManager {
        require(newRate > 0, "Rate must be positive");
        
        uint256 oldRate = exchangeRate;
        exchangeRate = newRate;
        
        emit ExchangeRateUpdated(oldRate, newRate);
    }
    
    /**
     * @dev Update manager (only owner)
     */
    function setManager(address newManager) external onlyOwner {
        require(newManager != address(0), "Manager cannot be zero address");
        
        address oldManager = manager;
        manager = newManager;
        
        emit ManagerUpdated(oldManager, newManager);
    }
    
    /**
     * @dev Update default time lock (only owner)
     */
    function setDefaultTimeLock(uint256 newTimeLock) external onlyOwner {
        require(newTimeLock > 0, "Time lock must be positive");
        defaultTimeLock = newTimeLock;
    }
    
    /**
     * @dev Emergency pause (only owner)
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause (only owner)
     */
    function unpause() external onlyOwner {
        _unpause();
    }
    
    /**
     * @dev Emergency withdraw native coins (only owner)
     */
    function emergencyWithdraw() external onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }
    
    /**
     * @dev Get cross-chain swap details
     */
    function getCrossChainSwap(bytes32 swapId) external view returns (
        bytes32 hashLock,
        uint256 timeLock,
        address sender,
        address recipient,
        uint256 amount,
        bool completed,
        bool refunded,
        uint256 createdAt,
        bool isManagerLocked
    ) {
        CrossChainSwap storage swap = crossChainSwaps[swapId];
        return (
            swap.hashLock,
            swap.timeLock,
            swap.sender,
            swap.recipient,
            swap.amount,
            swap.completed,
            swap.refunded,
            swap.createdAt,
            swap.isManagerLocked
        );
    }

    /**
     * @dev Get manager lock details
     */
    function getManagerLock(bytes32 hashLock) external view returns (
        bytes32 hash,
        uint256 timeLock,
        address recipient,
        uint256 amount,
        bool completed,
        bool refunded,
        uint256 createdAt
    ) {
        ManagerLock storage lock = managerLocks[hashLock];
        return (
            lock.hashLock,
            lock.timeLock,
            lock.recipient,
            lock.amount,
            lock.completed,
            lock.refunded,
            lock.createdAt
        );
    }
    
    /**
     * @dev Check if swap is expired
     */
    function isSwapExpired(bytes32 swapId) external view returns (bool) {
        return block.number > crossChainSwaps[swapId].timeLock;
    }
    
    /**
     * @dev Get contract native coin balance
     */
    function getNativeBalance() external view returns (uint256) {
        return address(this).balance;
    }
    
    // Receive function to accept native coins
    receive() external payable {}
}
