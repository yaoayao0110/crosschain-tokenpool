const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("Starting CrossChainTokenPool deployment...");
  
  // Get network info
  const network = await ethers.provider.getNetwork();
  console.log(`Deploying to network: ${network.name} (Chain ID: ${network.chainId})`);
  
  // Get deployer account
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying with account: ${deployer.address}`);
  console.log(`Account balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH`);
  
  // Deployment parameters
  const deploymentParams = getDeploymentParams(network.chainId);
  
  console.log("Deployment parameters:");
  console.log(`- Token Name: ${deploymentParams.name}`);
  console.log(`- Token Symbol: ${deploymentParams.symbol}`);
  console.log(`- Manager: ${deploymentParams.manager}`);
  console.log(`- Exchange Rate: ${deploymentParams.exchangeRate}`);
  console.log(`- Default Time Lock: ${deploymentParams.defaultTimeLock}`);
  
  // Deploy contract
  const CrossChainTokenPool = await ethers.getContractFactory("CrossChainTokenPool");
  
  console.log("Deploying CrossChainTokenPool...");
  const tokenPool = await CrossChainTokenPool.deploy(
    deploymentParams.name,
    deploymentParams.symbol,
    deploymentParams.manager,
    deploymentParams.exchangeRate,
    deploymentParams.defaultTimeLock
  );
  
  await tokenPool.waitForDeployment();
  const contractAddress = await tokenPool.getAddress();
  
  console.log(`CrossChainTokenPool deployed to: ${contractAddress}`);
  
  // Wait for a few confirmations
  console.log("Waiting for confirmations...");
  await tokenPool.deploymentTransaction().wait(3);
  
  // Verify deployment
  console.log("Verifying deployment...");
  const deployedName = await tokenPool.name();
  const deployedSymbol = await tokenPool.symbol();
  const deployedManager = await tokenPool.manager();
  const deployedOwner = await tokenPool.owner();
  
  console.log("Deployment verification:");
  console.log(`- Name: ${deployedName}`);
  console.log(`- Symbol: ${deployedSymbol}`);
  console.log(`- Manager: ${deployedManager}`);
  console.log(`- Owner: ${deployedOwner}`);
  
  // Save deployment info
  const deploymentInfo = {
    network: network.name,
    chainId: network.chainId.toString(),
    contractAddress: contractAddress,
    deployerAddress: deployer.address,
    deploymentParams: deploymentParams,
    deploymentTime: new Date().toISOString(),
    transactionHash: tokenPool.deploymentTransaction().hash
  };
  
  saveDeploymentInfo(deploymentInfo);
  
  // Generate environment variables
  generateEnvVars(network.chainId, contractAddress);
  
  console.log("\n=== Deployment Summary ===");
  console.log(`Network: ${network.name}`);
  console.log(`Contract Address: ${contractAddress}`);
  console.log(`Transaction Hash: ${tokenPool.deploymentTransaction().hash}`);
  console.log(`Gas Used: ${(await tokenPool.deploymentTransaction().wait()).gasUsed}`);
  
  console.log("\n=== Next Steps ===");
  console.log("1. Update your .env file with the new contract address");
  console.log("2. Verify the contract on block explorer if needed");
  console.log("3. Configure the Python backend with the new address");
  console.log("4. Test the deployment with basic operations");
  
  // If on testnet, perform initial setup
  if (isTestnet(network.chainId)) {
    console.log("\n=== Testnet Setup ===");
    await performTestnetSetup(tokenPool, deployer);
  }
}

function getDeploymentParams(chainId) {
  const params = {
    // Default parameters
    name: "CrossChain Token",
    symbol: "CCT",
    manager: process.env.MANAGER_ADDRESS || "0x0000000000000000000000000000000000000000",
    exchangeRate: ethers.parseEther("1000"), // 1 ETH/BNB = 1000 tokens
    defaultTimeLock: 100 // 100 blocks
  };
  
  // Chain-specific parameters
  switch (chainId.toString()) {
    case "1": // Ethereum Mainnet
      params.name = "CrossChain ETH Token";
      params.symbol = "CCETH";
      params.exchangeRate = ethers.parseEther("2000"); // Higher rate for mainnet
      params.defaultTimeLock = 200; // More blocks for mainnet
      break;
      
    case "56": // BSC Mainnet
      params.name = "CrossChain BNB Token";
      params.symbol = "CCBNB";
      params.exchangeRate = ethers.parseEther("1500");
      params.defaultTimeLock = 300; // More blocks due to faster BSC blocks
      break;
      
    case "11155111": // Sepolia Testnet
      params.name = "CrossChain ETH Token (Testnet)";
      params.symbol = "CCETH-T";
      params.exchangeRate = ethers.parseEther("1000");
      params.defaultTimeLock = 50; // Fewer blocks for testing
      break;
      
    case "97": // BSC Testnet
      params.name = "CrossChain BNB Token (Testnet)";
      params.symbol = "CCBNB-T";
      params.exchangeRate = ethers.parseEther("1000");
      params.defaultTimeLock = 100;
      break;
      
    case "1337": // Hardhat local
      params.name = "CrossChain Token (Local)";
      params.symbol = "CCT-L";
      params.exchangeRate = ethers.parseEther("100");
      params.defaultTimeLock = 10;
      break;
  }
  
  // Validate manager address
  if (params.manager === "0x0000000000000000000000000000000000000000") {
    console.warn("WARNING: Manager address not set! Using deployer as manager.");
    // Will be set to deployer in the deployment
  }
  
  return params;
}

function isTestnet(chainId) {
  const testnets = ["11155111", "97", "1337"]; // Sepolia, BSC Testnet, Hardhat
  return testnets.includes(chainId.toString());
}

async function performTestnetSetup(tokenPool, deployer) {
  try {
    console.log("Performing testnet setup...");
    
    // If manager is not set, set deployer as manager
    const currentManager = await tokenPool.manager();
    if (currentManager === "0x0000000000000000000000000000000000000000") {
      console.log("Setting deployer as manager...");
      await tokenPool.setManager(deployer.address);
      console.log(`Manager set to: ${deployer.address}`);
    }
    
    // Add some initial liquidity for testing
    console.log("Adding initial liquidity...");
    const initialLiquidity = ethers.parseEther("10"); // 10 ETH/BNB
    await tokenPool.swapNativeForToken({ value: initialLiquidity });
    console.log(`Added ${ethers.formatEther(initialLiquidity)} native tokens as liquidity`);
    
    // Get token balance
    const tokenBalance = await tokenPool.balanceOf(deployer.address);
    console.log(`Received ${ethers.formatEther(tokenBalance)} tokens`);
    
    console.log("Testnet setup completed!");
    
  } catch (error) {
    console.error("Testnet setup failed:", error.message);
  }
}

function saveDeploymentInfo(info) {
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  
  // Create deployments directory if it doesn't exist
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }
  
  // Save deployment info
  const filename = `${info.network}-${info.chainId}.json`;
  const filepath = path.join(deploymentsDir, filename);
  
  fs.writeFileSync(filepath, JSON.stringify(info, null, 2));
  console.log(`Deployment info saved to: ${filepath}`);
}

function generateEnvVars(chainId, contractAddress) {
  const envVars = [];
  
  switch (chainId.toString()) {
    case "1":
      envVars.push(`ETH_POOL_ADDRESS=${contractAddress}`);
      break;
    case "56":
      envVars.push(`BSC_POOL_ADDRESS=${contractAddress}`);
      break;
    case "11155111":
      envVars.push(`SEPOLIA_POOL_ADDRESS=${contractAddress}`);
      break;
    case "97":
      envVars.push(`BSC_TESTNET_POOL_ADDRESS=${contractAddress}`);
      break;
    case "1337":
      envVars.push(`LOCAL_POOL_ADDRESS=${contractAddress}`);
      break;
  }
  
  if (envVars.length > 0) {
    console.log("\n=== Environment Variables ===");
    console.log("Add these to your .env file:");
    envVars.forEach(envVar => console.log(envVar));
  }
}

// Handle errors
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:", error);
    process.exit(1);
  });
