const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("Correct HTLC Order: Alice Initiates, Manager Responds", function () {
  let ethPool, bscPool;
  let owner, manager, alice, bob;
  let exchangeRate = ethers.parseEther("1000"); // 1 ETH = 1000 tokens
  let defaultTimeLock = 100; // 100 blocks
  let secret, hashLock;

  beforeEach(async function () {
    [owner, manager, alice, bob] = await ethers.getSigners();

    const CrossChainTokenPool = await ethers.getContractFactory("CrossChainTokenPool");
    
    // Deploy ETH pool
    ethPool = await CrossChainTokenPool.deploy(
      "CrossChain ETH Token",
      "CCETH",
      manager.address,
      exchangeRate,
      defaultTimeLock
    );
    await ethPool.waitForDeployment();

    // Deploy BSC pool
    bscPool = await CrossChainTokenPool.deploy(
      "CrossChain BNB Token", 
      "CCBNB",
      manager.address,
      exchangeRate,
      defaultTimeLock
    );
    await bscPool.waitForDeployment();

    // Alice chooses secret and generates hash lock
    secret = ethers.randomBytes(32);
    hashLock = ethers.keccak256(secret);

    // Setup: Alice gets tokens on ETH chain
    await ethPool.connect(alice).swapNativeForToken({ 
      value: ethers.parseEther("1") 
    });

    // Setup: Manager gets tokens on BSC chain for responding
    await bscPool.connect(manager).swapNativeForToken({ 
      value: ethers.parseEther("1") 
    });
  });

  describe("Correct HTLC Order", function () {
    it("Should follow correct order: Alice initiates, Manager responds, Alice reveals, Bob claims", async function () {
      const swapAmount = ethers.parseEther("500"); // 500 tokens
      const timeLockBlocks = 50;

      // Step 1: Alice initiates cross-chain swap on ETH chain (chooses secret)
      const tx = await ethPool.connect(alice).initiateCrossChain(
        hashLock,  // Alice's hash lock
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log => 
        log.fragment && log.fragment.name === "CrossChainInitiated"
      );
      const swapId = event.args.swapId;

      // Verify Alice's initiation
      expect(event.args.hashLock).to.equal(hashLock);
      expect(event.args.sender).to.equal(alice.address);
      expect(event.args.recipient).to.equal(bob.address);
      expect(event.args.amount).to.equal(swapAmount);

      // Verify Alice's tokens are locked
      expect(await ethPool.balanceOf(alice.address)).to.equal(
        ethers.parseEther("500") // 1000 - 500
      );

      // Step 2: Manager observes Alice's swap and responds on BSC chain
      await expect(
        bscPool.connect(manager).managerRespondToCrossChain(
          hashLock,  // Same hash lock as Alice used
          bob.address,
          swapAmount,
          timeLockBlocks - 10  // Shorter time lock for safety
        )
      ).to.emit(bscPool, "ManagerLockCreated")
       .withArgs(hashLock, bob.address, swapAmount);

      // Verify manager lock
      const managerLock = await bscPool.getManagerLock(hashLock);
      expect(managerLock.recipient).to.equal(bob.address);
      expect(managerLock.amount).to.equal(swapAmount);
      expect(managerLock.completed).to.be.false;

      // Step 3: Alice reveals secret on ETH chain (burns tokens)
      await expect(
        ethPool.connect(alice).completeCrossChain(swapId, secret)
      ).to.emit(ethPool, "CrossChainCompleted")
       .withArgs(swapId, secret);

      // Verify Alice's tokens are burned
      expect(await ethPool.balanceOf(await ethPool.getAddress())).to.equal(0);
      expect(await ethPool.totalSupply()).to.equal(ethers.parseEther("500")); // 1000 - 500 burned

      // Step 4: Bob uses Alice's revealed secret to claim tokens on BSC chain
      await expect(
        bscPool.connect(bob).completeManagerLock(hashLock, secret)
      ).to.emit(bscPool, "ManagerLockCompleted")
       .withArgs(hashLock, secret);

      // Verify Bob received tokens
      expect(await bscPool.balanceOf(bob.address)).to.equal(swapAmount);

      // Verify final states
      const completedSwap = await ethPool.getCrossChainSwap(swapId);
      const completedLock = await bscPool.getManagerLock(hashLock);
      
      expect(completedSwap.completed).to.be.true;
      expect(completedLock.completed).to.be.true;
    });

    it("Should emit detailed CrossChainInitiated event for manager monitoring", async function () {
      const swapAmount = ethers.parseEther("300");
      const timeLockBlocks = 60;

      const tx = await ethPool.connect(alice).initiateCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log =>
        log.fragment && log.fragment.name === "CrossChainInitiated"
      );

      // Verify event details
      expect(event).to.not.be.undefined;
      expect(event.args.hashLock).to.equal(hashLock);
      expect(event.args.sender).to.equal(alice.address);
      expect(event.args.recipient).to.equal(bob.address);
      expect(event.args.amount).to.equal(swapAmount);
      expect(event.args.timeLock).to.be.gt(0);
    });

    it("Should prevent manager from using same hash lock twice", async function () {
      const swapAmount = ethers.parseEther("200");
      const timeLockBlocks = 40;

      // Alice initiates
      await ethPool.connect(alice).initiateCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      // Manager responds first time
      await bscPool.connect(manager).managerRespondToCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      // Manager tries to respond again with same hash lock
      await expect(
        bscPool.connect(manager).managerRespondToCrossChain(
          hashLock,
          bob.address,
          swapAmount,
          timeLockBlocks
        )
      ).to.be.revertedWith("Hash lock already used");
    });

    it("Should allow refund if Alice doesn't reveal secret", async function () {
      const swapAmount = ethers.parseEther("400");
      const timeLockBlocks = 10; // Short time lock for testing

      // Step 1: Alice initiates
      const tx = await ethPool.connect(alice).initiateCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log => 
        log.fragment && log.fragment.name === "CrossChainInitiated"
      );
      const swapId = event.args.swapId;

      // Step 2: Manager responds
      await bscPool.connect(manager).managerRespondToCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks - 5  // Even shorter for manager
      );

      // Step 3: Wait for time locks to expire
      await time.advanceBlockTo((await time.latestBlock()) + timeLockBlocks + 1);

      // Step 4: Alice can refund her tokens
      await expect(
        ethPool.connect(alice).refundCrossChain(swapId)
      ).to.emit(ethPool, "CrossChainRefunded")
       .withArgs(swapId);

      // Step 5: Manager can refund locked tokens
      await expect(
        bscPool.connect(manager).refundManagerLock(hashLock)
      ).to.emit(bscPool, "ManagerLockRefunded")
       .withArgs(hashLock);

      // Verify refunds
      expect(await ethPool.balanceOf(alice.address)).to.equal(ethers.parseEther("1000"));
      expect(await bscPool.balanceOf(manager.address)).to.equal(ethers.parseEther("1000"));
    });

    it("Should work with different time locks for user and manager", async function () {
      const swapAmount = ethers.parseEther("350");
      const userTimeLock = 100;
      const managerTimeLock = 80; // Manager has shorter time lock

      // Alice initiates with longer time lock
      const tx = await ethPool.connect(alice).initiateCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        userTimeLock
      );

      const receipt = await tx.wait();
      const event = receipt.logs.find(log => 
        log.fragment && log.fragment.name === "CrossChainInitiated"
      );
      const swapId = event.args.swapId;

      // Manager responds with shorter time lock (safety margin)
      await bscPool.connect(manager).managerRespondToCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        managerTimeLock
      );

      // Complete the swap
      await ethPool.connect(alice).completeCrossChain(swapId, secret);
      await bscPool.connect(bob).completeManagerLock(hashLock, secret);

      // Verify completion
      expect(await ethPool.balanceOf(alice.address)).to.equal(ethers.parseEther("650"));
      expect(await bscPool.balanceOf(bob.address)).to.equal(swapAmount);
    });

    it("Should prevent non-manager from responding to swaps", async function () {
      const swapAmount = ethers.parseEther("250");
      const timeLockBlocks = 50;

      // Alice initiates
      await ethPool.connect(alice).initiateCrossChain(
        hashLock,
        bob.address,
        swapAmount,
        timeLockBlocks
      );

      // Non-manager tries to respond
      await expect(
        bscPool.connect(alice).managerRespondToCrossChain(
          hashLock,
          bob.address,
          swapAmount,
          timeLockBlocks
        )
      ).to.be.revertedWith("Only manager can call this function");
    });
  });
});
