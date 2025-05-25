from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.token import _TOKEN_PROGRAM_ID
from solders.system_program import _ID
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from spl.token.instructions import get_associated_token_address, create_idempotent_associated_token_account
import asyncio
import base58
import hashlib
from solana.rpc.types import TxOpts
from borsh_construct import CStruct, String, U64
from anchorpy.borsh_extension import BorshPubkey
import os
from dotenv import load_dotenv
from typing import Tuple, Dict, List
from src.models.solana_client import SolanaAsyncClient
from src.models.token import TokenConfig

# Constants
PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
TOKEN_MINT_AUTHORITY = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
CONFIG = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
EVENT_AUTHORITY = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
RENT_PROGRAM = "SysvarRent111111111111111111111111111111111"



def load_keypair_from_private_key(private_key_str: str) -> Keypair:
    """Load keypair from private key string."""
    try:
        private_key_bytes = base58.b58decode(private_key_str)
        return Keypair.from_bytes(private_key_bytes)
    except Exception as e:
        raise Exception(f"Failed to load keypair: {str(e)}")

def calculate_tokens_receive(sol_amount, previous_sol=30, slippage=25) -> Dict[any, any]:
    """
    Calculate tokens received for given SOL amount
    """
    LAMPORTS_PER_SOL = 10**9
    TOKEN_DECIMALS = 10**6
    
    INITIAL_TOKENS = 1073000191 * TOKEN_DECIMALS  # Convert to token units
    K = 32190005730 * TOKEN_DECIMALS  # Convert to token units
    
    # Convert SOL to lamports
    previous_lamports = int(previous_sol * LAMPORTS_PER_SOL)
    new_lamports = previous_lamports + int(sol_amount * LAMPORTS_PER_SOL)
    
    # Calculate tokens
    current_tokens = INITIAL_TOKENS - (K / (previous_lamports / LAMPORTS_PER_SOL))
    new_tokens = INITIAL_TOKENS - (K / (new_lamports / LAMPORTS_PER_SOL))
    
    # Calculate difference in tokens
    tokens_received = (new_tokens - current_tokens) / TOKEN_DECIMALS
    max_sol_cost = sol_amount * (1 + slippage/100)
    
    return {
        "amount": int(tokens_received * TOKEN_DECIMALS),
        "max_sol_cost": int(max_sol_cost * LAMPORTS_PER_SOL)
    }

async def get_inx_create_associated_token_account(mint: Keypair, owner: Keypair) -> Instruction:
    """Get instruction for creating associated token account."""
    return create_idempotent_associated_token_account(
        payer=owner.pubkey(),
        owner=owner.pubkey(),
        mint=mint.pubkey()
    )

async def get_inx_create_pump_fun(
    program_id: Pubkey,
    payer: Keypair,
    creator_pubkey: Pubkey,
    token_config: TokenConfig
) -> Tuple[Instruction, Keypair]:
    """Get instruction for creating PumpFun token."""
    discriminator = f"global:create".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    
    create_token_layout = CStruct(
        "name" / String,
        "symbol" / String,
        "uri" / String,
        "creator" / BorshPubkey,
    )
    
    instruction_data = discriminator_hash + create_token_layout.build({
        "name": token_config.name,
        "symbol": token_config.symbol,
        "uri": token_config.uri,
        "creator": creator_pubkey
    })

    mint_keypair = Keypair()
    token_mint_authority = Pubkey.from_string(TOKEN_MINT_AUTHORITY)
    
    seed_curve = [b"bonding-curve", bytes(mint_keypair.pubkey())]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    vault_pda = get_associated_token_address(curve_pda, mint_keypair.pubkey())
    
    seed_metadata = [b"metadata", bytes(Pubkey.from_string(METADATA_PROGRAM_ID)), bytes(mint_keypair.pubkey())]
    token_metadata_pda, _ = Pubkey.find_program_address(seed_metadata, Pubkey.from_string(METADATA_PROGRAM_ID))
    
    accounts = [
        AccountMeta(mint_keypair.pubkey(), True, True),  # Config
        AccountMeta(token_mint_authority, False, False),  # Payer
        AccountMeta(curve_pda, False, True),  # Mint
        AccountMeta(vault_pda, False, True),  # Token Mint Authority
        AccountMeta(Pubkey.from_string(CONFIG), False, False),  # Curve
        AccountMeta(Pubkey.from_string(METADATA_PROGRAM_ID), False, False),  # Vault
        AccountMeta(token_metadata_pda, False, True),  # Token Metadata
        AccountMeta(payer.pubkey(), True, True),  # Payer
        AccountMeta(_ID, False, False),  # System Program
        AccountMeta(_TOKEN_PROGRAM_ID, False, False),  # Token Program
        AccountMeta(Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM), False, False),  # Associated Token Program
        AccountMeta(Pubkey.from_string(RENT_PROGRAM), False, False),  # Rent Program
        AccountMeta(Pubkey.from_string(EVENT_AUTHORITY), False, False),  # Event Authority
        AccountMeta(program_id, False, False),  # Program ID
    ]

    return Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    ), mint_keypair

async def get_inx_buy_token(
    program_id: Pubkey,
    buyer: Keypair,
    mint: Pubkey,
    buy_args: Dict[any, any],
    creator_pubkey: Pubkey
) -> Instruction:
    """Get instruction for buying tokens."""
    discriminator = f"global:buy".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    
    buy_token_layout = CStruct(
        "amount" / U64,
        "max_sol_cost" / U64,
    )
    instruction_data = discriminator_hash + buy_token_layout.build(buy_args)

    creator_vault_pda, _ = Pubkey.find_program_address(
        [b"creator-vault", bytes(creator_pubkey)], program_id)
    
    seed_curve = [b"bonding-curve", bytes(mint)]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    vault_pda = get_associated_token_address(curve_pda, mint)
    associated_user_ata = get_associated_token_address(buyer.pubkey(), mint)

    accounts = [
        AccountMeta(Pubkey.from_string(CONFIG), False, False),  # Config
        AccountMeta(Pubkey.from_string("68yFSZxzLWJXkxxRGydZ63C6mHx1NLEDWmwN9Lb5yySg"), False, True),  # Buyer
        AccountMeta(mint, False, True),  # Mint
        AccountMeta(curve_pda, False, True),  # Vault
        AccountMeta(vault_pda, False, True),  # User ATA
        AccountMeta(associated_user_ata, False, True),
        AccountMeta(buyer.pubkey(), True, True),
        AccountMeta(_ID, False, False),
        AccountMeta(_TOKEN_PROGRAM_ID, False, False),
        AccountMeta(creator_vault_pda, False, True),
        AccountMeta(Pubkey.from_string(EVENT_AUTHORITY), False, False),
        AccountMeta(program_id, False, False),
    ]

    return Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    )

async def get_tx(instructions: List[Instruction], signers: List[Keypair], recent_blockhash: bytes) -> Transaction:
    """Create and sign a transaction."""
    message = Message.new_with_blockhash(
        instructions,
        signers[0].pubkey(),
        recent_blockhash
    )
    transaction = Transaction(
        from_keypairs=signers,
        message=message,
        recent_blockhash=recent_blockhash
    )
    return transaction

async def main():
    """Main function to execute the token creation and buying process."""
    load_dotenv()
    
    # Initialize client
    client = await SolanaAsyncClient.get_client()


    try:
        # Load keypairs
        account_a = load_keypair_from_private_key(
            base58.b58encode(bytes([int(byte) for byte in os.getenv("account_a_pk").split(",")])).decode('ascii')
        )
        account_b = load_keypair_from_private_key(
            base58.b58encode(bytes([int(byte) for byte in os.getenv("account_b_pk").split(",")])).decode('ascii')
        )
        
        print(f"Account A public key: {account_a.pubkey()}")
        print(f"Account B public key: {account_b.pubkey()}")

        program_id = Pubkey.from_string(PROGRAM_ID)
        
        # Verify program account exists
        program_info = await client.get_account_info(program_id)
        if not program_info.value:
            raise Exception(f"Program account {program_id} not found")

        recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
        
        # Create token
        token_config = TokenConfig("Pump Fun V2", "PUMP", "https://pumpfun.io")
        ix_create_pump_fun, mint_keypair = await get_inx_create_pump_fun(
            program_id,
            account_a,
            account_a.pubkey(),
            token_config
        )

        # Create associated token accounts
        ix_create_ata_1 = await get_inx_create_associated_token_account(mint_keypair, account_a)
        ix_create_ata_2 = await get_inx_create_associated_token_account(mint_keypair, account_b)

        # Buy tokens
        ix_buy_token_1 = await get_inx_buy_token(
            program_id,
            account_a,
            mint_keypair.pubkey(),
            calculate_tokens_receive(0.0001),
            account_a.pubkey()
        )

        ix_buy_token_2 = await get_inx_buy_token(
            program_id,
            account_b,
            mint_keypair.pubkey(),
            calculate_tokens_receive(0.0002),
            account_a.pubkey()
        )

        # Build and send transaction
        ixs = [
            ix_create_pump_fun,
            ix_create_ata_1,
            ix_buy_token_1,
            ix_create_ata_2,
            ix_buy_token_2
        ]
        
        tx = await get_tx(ixs, [account_a, account_b, mint_keypair], recent_blockhash)
        sim_result = await client.send_transaction(tx, opts=TxOpts(skip_preflight=False))
        print(f"Transaction result: {sim_result}")

    finally:
        await SolanaAsyncClient.close_client()

if __name__ == "__main__":
    asyncio.run(main())
