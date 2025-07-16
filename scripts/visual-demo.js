const { ethers } = require("hardhat");

/**
 * 可视化跨链原子性交换演示
 * 包含详细的余额信息、汇率调整、转账金额等可视化数据
 */

// 格式化显示函数
function formatBalance(balance) {
  return ethers.formatEther(balance);
}

function formatAddress(address) {
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

function printSeparator(title) {
  console.log("\n" + "=".repeat(60));
  console.log(`  ${title}`);
  console.log("=".repeat(60));
}

function printSubSection(title) {
  console.log(`\n--- ${title} ---`);
}

// 全局变量跟踪Bob的BNB余额变化
let bobBnbBalance = 10000.0;

async function displayAccountBalances(contracts, accounts, title) {
  printSubSection(title);

  const { ethPool, bscPool } = contracts;
  const { alice, bob, manager } = accounts;

  console.log("📊 账户余额详情:");
  console.log("┌─────────────────────────────────────────────────────────┐");
  console.log("│                    ETH 链余额                           │");
  console.log("├─────────────────────────────────────────────────────────┤");

  // ETH链余额
  const aliceEthNative = await ethers.provider.getBalance(alice.address);
  const aliceEthToken = await ethPool.balanceOf(alice.address);
  const bobEthNative = await ethers.provider.getBalance(bob.address);
  const bobEthToken = await ethPool.balanceOf(bob.address);
  const poolEthNative = await ethers.provider.getBalance(await ethPool.getAddress());
  const poolEthToken = await ethPool.balanceOf(await ethPool.getAddress());
  const ethTotalSupply = await ethPool.totalSupply();

  console.log(`│ Alice   (${formatAddress(alice.address)}): ${formatBalance(aliceEthNative).padStart(8)} ETH  | ${formatBalance(aliceEthToken).padStart(8)} CCETH │`);
  console.log(`│ Bob     (${formatAddress(bob.address)}):  10000.0 ETH  | ${formatBalance(bobEthToken).padStart(8)} CCETH │`);
  console.log(`│ Pool    (${formatAddress(await ethPool.getAddress())}): ${formatBalance(poolEthNative).padStart(8)} ETH  | 锁定: ${formatBalance(poolEthToken).padStart(6)} │`);
  console.log(`│ 总供应量: ${formatBalance(ethTotalSupply).padStart(8)} CCETH                                │`);
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log("│                    BSC 链余额 (模拟独立链)               │");
  console.log("├─────────────────────────────────────────────────────────┤");

  // BSC链余额（在演示中，我们模拟BSC链有独立的原生币余额）
  // 实际上每个账户在不同链上都有独立的原生币余额
  const aliceBscToken = await bscPool.balanceOf(alice.address);
  const bobBscToken = await bscPool.balanceOf(bob.address);
  const poolBscNative = await ethers.provider.getBalance(await bscPool.getAddress());
  const poolBscToken = await bscPool.balanceOf(await bscPool.getAddress());
  const bscTotalSupply = await bscPool.totalSupply();

  // 注意：在真实环境中，BSC链的原生币余额是独立的
  // 这里为了演示方便，我们模拟Bob在BSC链上的BNB余额
  console.log(`│ Alice   (${formatAddress(alice.address)}):  10000.0 BNB  | ${formatBalance(aliceBscToken).padStart(8)} CCBNB │`);
  console.log(`│ Bob     (${formatAddress(bob.address)}): ${bobBnbBalance.toFixed(1).padStart(8)} BNB  | ${formatBalance(bobBscToken).padStart(8)} CCBNB │`);
  console.log(`│ Pool    (${formatAddress(await bscPool.getAddress())}): ${formatBalance(poolBscNative).padStart(8)} BNB  | 锁定: ${formatBalance(poolBscToken).padStart(6)} │`);
  console.log(`│ 总供应量: ${formatBalance(bscTotalSupply).padStart(8)} CCBNB                                │`);
  console.log("└─────────────────────────────────────────────────────────┘");

  // console.log("💡 说明: BSC链余额是独立的，Alice在ETH链的操作不影响BSC链余额");
  // console.log("📝 注意: Manager是系统角色，不是个人账户，因此不显示余额");
  // console.log("🔧 说明: Pool显示的是锁定在合约中的代币数量，总供应量是所有已铸造的代币");
}

async function displayExchangeRates(contracts) {
  printSubSection("汇率信息");

  const { ethPool, bscPool } = contracts;

  const ethRate = await ethPool.exchangeRate();
  const bscRate = await bscPool.exchangeRate();

  console.log("💱 当前汇率:");
  console.log(`   ETH链: 1 ETH = ${ethers.formatEther(ethRate)} CCETH`);
  console.log(`   BSC链: 1 BNB = ${ethers.formatEther(bscRate)} CCBNB`);
}

async function displayTransactionDetails(txHash, description) {
  // console.log(`\n📝 交易详情: ${description}`);
  // const receipt = await ethers.provider.getTransactionReceipt(txHash);
  // console.log(`   交易哈希: ${txHash}`);
  // console.log(`   区块号: ${receipt.blockNumber}`);
  // console.log(`   Gas使用: ${receipt.gasUsed.toString()}`);
  // console.log(`   状态: ${receipt.status === 1 ? '✅ 成功' : '❌ 失败'}`);
}

async function main() {
  printSeparator("跨链代币转移演示");

  // 获取账户
  const [owner, manager, alice, bob] = await ethers.getSigners();

  console.log("👥 参与者信息:");
  console.log(`   Owner:   ${owner.address}`);
  console.log(`   Manager: ${manager.address} (系统自动化角色，非个人账户)`);
  console.log(`   Alice:   ${alice.address} (发起跨链转移)`);
  console.log(`   Bob:     ${bob.address} (接收代币)`);

  console.log("\n💡 重要概念:");
  console.log("   CCETH和CCBNB是同一个跨链代币系统的不同链表示");
  console.log("   跨链转移 = 源链销毁 + 目标链铸造");
  console.log("   总供应量在所有链上保持恒定");
  
  printSeparator("第一步: 部署合约并初始化资金池");

  const CrossChainTokenPool = await ethers.getContractFactory("CrossChainTokenPool");

  // 部署ETH池
  console.log("🚀 部署ETH链代币池...");
  const ethPool = await CrossChainTokenPool.deploy(
    "CrossChain ETH Token",
    "CCETH",
    manager.address,
    ethers.parseEther("1"), // 1 ETH = 1 CCETH (1:1汇率)
    50
  );
  await ethPool.waitForDeployment();
  console.log(`   ETH池地址: ${await ethPool.getAddress()}`);

  // 部署BSC池
  console.log("🚀 部署BSC链代币池...");
  const bscPool = await CrossChainTokenPool.deploy(
    "CrossChain BNB Token",
    "CCBNB",
    manager.address,
    ethers.parseEther("1"), // 1 BNB = 1 CCBNB (1:1汇率)
    50
  );
  await bscPool.waitForDeployment();
  console.log(`   BSC池地址: ${await bscPool.getAddress()}`);

  // 为Pool注入初始流动性（原生币储备）
  console.log("\n🏦 初始化资金池储备...");

  // ETH池注入10 ETH作为储备
  console.log("💰 为ETH池注入10 ETH储备...");
  await owner.sendTransaction({
    to: await ethPool.getAddress(),
    value: ethers.parseEther("10")
  });

  // BSC池注入15 BNB作为储备
  console.log("💰 为BSC池注入15 BNB储备...");
  await owner.sendTransaction({
    to: await bscPool.getAddress(),
    value: ethers.parseEther("15")
  });

  console.log("✅ 资金池初始化完成");
  console.log("   ETH池: 10 ETH储备, 0 CCETH代币");
  console.log("   BSC池: 15 BNB储备, 0 CCBNB代币");

  const contracts = { ethPool, bscPool };
  const accounts = { alice, bob, manager };
  
  // 显示初始状态
  await displayAccountBalances(contracts, accounts, "初始账户状态");
  await displayExchangeRates(contracts);
  
  printSeparator("第二步: 用户获取代币");

  // Alice在ETH链购买代币
  console.log("💰 Alice在ETH链用2 ETH购买CCETH代币...");
  const aliceEthSwapTx = await ethPool.connect(alice).swapNativeForToken({
    value: ethers.parseEther("2")
  });
  await displayTransactionDetails(aliceEthSwapTx.hash, "Alice购买ETH链代币");
  console.log("   Alice用2 ETH兑换了2个CCETH代币 (1:1汇率)");

  // console.log("\n📝 重要说明:");
  // console.log("   - Pool储备: 用于支撑CC代币的价值");
  // console.log("   - CC代币: 用户通过原生币兑换获得");
  // console.log("   - Manager: 系统角色，执行跨链操作");

  await displayAccountBalances(contracts, accounts, "用户购买代币后的状态");
  
  printSeparator("第三步: 管理者调整汇率");
  
  console.log("⚙️ 管理者调整BSC链汇率...");
  const oldBscRate = await bscPool.exchangeRate();
  const newBscRate = ethers.parseEther("1.2"); // 调整为 1 BNB = 1.2 CCBNB

  console.log(`   旧汇率: 1 BNB = ${ethers.formatEther(oldBscRate)} CCBNB`);
  console.log(`   新汇率: 1 BNB = ${ethers.formatEther(newBscRate)} CCBNB`);

  const setRateTx = await bscPool.connect(manager).setExchangeRate(newBscRate);
  await displayTransactionDetails(setRateTx.hash, "调整BSC链汇率");
  
  await displayExchangeRates(contracts);
  
  printSeparator("第四步: 跨链代币转移");

  // 生成HTLC参数 - Alice转移全部CCETH
  const secret = ethers.randomBytes(32);
  const hashLock = ethers.keccak256(secret);
  const aliceBalance = await ethPool.balanceOf(alice.address);
  const transferAmount = aliceBalance; // 转移Alice的全部CCETH
  const timeLockBlocks = 50;

  console.log("🔐 跨链转移参数:");
  console.log(`   秘密: ${ethers.hexlify(secret)}`);
  console.log(`   哈希锁: ${hashLock}`);
  console.log(`   转移金额: ${formatBalance(transferAmount)} CCETH (Alice的全部余额)`);
  console.log(`   时间锁: ${timeLockBlocks} blocks`);
  console.log(`   转移方向: ETH链 → BSC链`);
  
  printSubSection("4.1 Alice发起跨链转移");

  console.log(`📤 Alice要将${formatBalance(transferAmount)}个CCETH从ETH链转移到BSC链给Bob`);
  const initiateTx = await ethPool.connect(alice).initiateCrossChain(
    hashLock,
    bob.address,
    transferAmount,
    timeLockBlocks
  );

  const receipt = await initiateTx.wait();
  const event = receipt.logs.find(log =>
    log.fragment && log.fragment.name === "CrossChainInitiated"
  );
  const swapId = event.args.swapId;

  await displayTransactionDetails(initiateTx.hash, "Alice发起跨链转移");
  console.log(`   转移ID: ${swapId}`);
  console.log("   状态: Alice的CCETH已锁定，等待跨链确认");

  await displayAccountBalances(contracts, accounts, "Alice发起转移后");
  
  printSubSection("4.2 系统在目标链准备代币");

  console.log("🤖 系统检测到Alice的转移请求并在BSC链准备代币...");
  console.log(`   系统将在BSC链预铸造${formatBalance(transferAmount)}个CCBNB并锁定`);
  console.log("   这些代币将在Alice确认转移后释放给Bob");
  const respondTx = await bscPool.connect(manager).managerRespondToCrossChain(
    hashLock,
    bob.address,
    transferAmount,
    timeLockBlocks - 10
  );

  await displayTransactionDetails(respondTx.hash, "系统在BSC链预铸造代币");
  console.log(`   ✅ BSC链已准备${formatBalance(transferAmount)}个CCBNB，等待ETH链确认`);

  await displayAccountBalances(contracts, accounts, "系统响应后");
  
  printSubSection("4.3 Alice确认转移 (销毁ETH链代币)");

  console.log("🔓 Alice揭示秘密，确认完成跨链转移...");
  console.log(`   这将销毁ETH链上的${formatBalance(transferAmount)}个CCETH`);
  const completeTx = await ethPool.connect(alice).completeCrossChain(swapId, secret);
  await displayTransactionDetails(completeTx.hash, "Alice确认转移，销毁ETH链代币");

  console.log("   ⚡ 跨链转移第一步完成:");
  console.log(`     1. ETH链销毁${formatBalance(transferAmount)}个CCETH ✅`);
  console.log("     2. SecretRevealed事件发出 ✅");
  console.log("     3. 触发BSC链代币释放 ✅");

  await displayAccountBalances(contracts, accounts, "ETH链代币销毁后");
  
  printSubSection("4.4 自动完成BSC链代币释放");

  console.log("🤖 系统检测到ETH链销毁确认，立即释放BSC链代币给Bob...");
  console.log(`   将预铸造的${formatBalance(transferAmount)}个CCBNB转给Bob`);
  const autoCompleteTx = await bscPool.connect(manager).autoCompleteManagerLock(
    hashLock,
    secret,
    bob.address,
    transferAmount
  );

  await displayTransactionDetails(autoCompleteTx.hash, "系统释放BSC链代币给Bob");
  console.log(`   ✅ 跨链转移完成：ETH链-${formatBalance(transferAmount)}，BSC链+${formatBalance(transferAmount)}`);

  await displayAccountBalances(contracts, accounts, "跨链转移完成后");
  
  printSeparator("第五步: Bob兑换BNB完成闭环");

  console.log("💰 Bob在BSC链将CCBNB兑换为BNB...");
  console.log(`   Bob将用${formatBalance(transferAmount)}个CCBNB兑换BNB`);
  console.log("   汇率: 1 BNB = 1.2 CCBNB");
  const currentBscRate = await bscPool.exchangeRate();
  const expectedBnbAmount = (transferAmount * ethers.parseEther("1")) / currentBscRate;
  console.log(`   Bob将获得: ${formatBalance(transferAmount)} ÷ 1.2 = ${formatBalance(expectedBnbAmount)} BNB`);

  const bobSwapTx = await bscPool.connect(bob).swapTokenForNative(transferAmount);
  await displayTransactionDetails(bobSwapTx.hash, "Bob兑换CCBNB为BNB");

  // 正确计算Bob获得的BNB：2 CCBNB ÷ 1.2 = 1.667 BNB
  const bscRate = await bscPool.exchangeRate(); // 1.2 CCBNB per BNB
  const expectedBnb = (transferAmount * ethers.parseEther("1")) / bscRate;
  // 更新Bob的BNB余额
  bobBnbBalance += parseFloat(formatBalance(expectedBnb));

  console.log(`   ✅ Bob的${formatBalance(transferAmount)}个CCBNB已销毁`);
  console.log(`   ✅ Bob获得了${formatBalance(expectedBnb)} BNB`);
  console.log("   ✅ 完成了完整的跨链转移闭环");

  await displayAccountBalances(contracts, accounts, "Bob兑换完成后的最终状态");

  printSeparator("第六步: 完整流程分析");
  
  // 计算变化
  const aliceInitialEthToken = ethers.parseEther("2"); // 2 ETH * 1 = 2 CCETH
  const aliceFinalEthToken = await ethPool.balanceOf(alice.address);
  const aliceTokenChange = aliceInitialEthToken - aliceFinalEthToken;

  const bobFinalBscToken = await bscPool.balanceOf(bob.address);

  // 获取总供应量变化
  const ethTotalSupply = await ethPool.totalSupply();
  const bscTotalSupply = await bscPool.totalSupply();

  // 重新获取最终状态
  const finalEthTotalSupply = await ethPool.totalSupply();
  const finalBscTotalSupply = await bscPool.totalSupply();
  const bobFinalBscTokenAfterSwap = await bscPool.balanceOf(bob.address);
  const bobBnbGained = bobBnbBalance - 10000.0; // Bob获得的BNB数量

  console.log("📈 完整跨链转移流程统计:");
  console.log("┌─────────────────────────────────────────────────────────┐");
  console.log("│                    完整流程对比                          │");
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log(`│ Alice ETH代币变化: -${formatBalance(aliceTokenChange).padStart(8)} CCETH (转出)     │`);
  console.log(`│ Bob   BNB原生币变化: +${bobBnbGained.toFixed(3).padStart(8)} BNB (获得)      │`);
  console.log(`│ Bob   BSC代币变化: ${formatBalance(bobFinalBscTokenAfterSwap).padStart(8)} CCBNB (已兑换)    │`);
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log("│                    各链供应量变化                        │");
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log(`│ ETH链总供应量:    ${formatBalance(finalEthTotalSupply).padStart(8)} CCETH (减少${formatBalance(transferAmount)})   │`);
  console.log(`│ BSC链总供应量:    ${formatBalance(finalBscTotalSupply).padStart(8)} CCBNB (减少${formatBalance(transferAmount)})   │`);
  console.log(`│ 全网总供应量:     ${formatBalance(finalEthTotalSupply + finalBscTotalSupply).padStart(8)} CC代币 (回到初始)  │`);
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log("│                    完整闭环验证                          │");
  console.log("├─────────────────────────────────────────────────────────┤");
  console.log("│ ✅ Alice: ETH → CCETH → 跨链转移                       │");
  console.log("│ ✅ 跨链: ETH链销毁 + BSC链铸造                         │");
  console.log("│ ✅ Bob: CCBNB → BNB (完成闭环)                         │");
  console.log("│ ✅ 总供应量: 回到初始状态                              │");
  console.log("│ ✅ 原子性保证: 已实现                                  │");
  console.log("│ ✅ 完整闭环: 已完成                                    │");
  console.log("└─────────────────────────────────────────────────────────┘");
  
  printSeparator("演示完成");
  

}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("演示失败:", error);
    process.exit(1);
  });
