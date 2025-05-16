# Solana SOL Transfer Script

This script provides functionality to transfer SOL between Solana accounts using the Solders and SolanaPy libraries.

## Features

- Create new Solana accounts
- Load existing accounts from private keys
- Check account balances
- Transfer SOL between accounts
- Error handling and proper connection management

## Installation

1. Clone this repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with the following variables (optional):
```
RPC_URL=your_custom_rpc_url
```

If not specified, the script will use the default Solana mainnet RPC URL.

## Usage

The script provides a `SolanaTransfer` class with the following main methods:

- `create_account()`: Create a new Solana account
- `load_keypair_from_private_key(private_key_str)`: Load an existing account from a private key
- `get_balance(pubkey)`: Get the SOL balance of an account
- `transfer_sol(from_keypair, to_pubkey, amount_sol)`: Transfer SOL between accounts

### Example

```python
from sol_transfer import SolanaTransfer
import asyncio

async def example():
    transfer_client = SolanaTransfer()
    
    # Create new accounts
    sender = await transfer_client.create_account()
    recipient = await transfer_client.create_account()
    
    # Transfer SOL
    signature = await transfer_client.transfer_sol(
        sender,
        str(recipient.pubkey()),
        0.1  # amount in SOL
    )
    
    await transfer_client.close()

asyncio.run(example())
```

## Running the Script

To run the example script:
```bash
python sol_transfer.py
```

## Notes

- The script uses async/await for better performance
- All amounts are specified in SOL (not lamports)
- The script includes proper error handling and connection cleanup
- Make sure to keep your private keys secure and never commit them to version control 