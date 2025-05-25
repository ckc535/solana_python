# Solana Transfer

A Python utility for Solana transfers and address lookup table operations.

## Setup with UV

1. Install UV if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create a virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
uv pip install -r uv.lock | uv pip install -r requirements.txt
```

The project includes a `uv.lock` file that locks the exact versions of all dependencies. This ensures reproducible builds across different environments.

## Environment Variables

Create a `.env` file with the following variables:
```
RPC_URL=https://api.devnet.solana.com
account_a_pk=your_private_key_here
account_b_pk=your_private_key_here
account_c_pk=your_private_key_here
account_d_pk=your_private_key_here
```

## Usage

Run the simple transfer example:
```bash
python sol_transfer_simple.py
```

Run the advanced transfer example with address lookup tables:
```bash
python sol_transfer.py
```

## Features

- Basic SOL transfers
- Batch SOL transfers
- Address Lookup Table operations
- Balance checking
- Keypair management 