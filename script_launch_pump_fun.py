from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.token import _TOKEN_PROGRAM_ID
from solders.system_program import TransferParams, transfer,_ID
from solders.compute_budget import set_compute_unit_price
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from spl.token.async_client import AsyncToken
from spl.token.instructions import get_associated_token_address, create_idempotent_associated_token_account
import asyncio
import base58
import hashlib
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from borsh_construct import CStruct, String, U64, Bytes
from anchorpy.borsh_extension import BorshPubkey
import os
from dotenv import load_dotenv
import requests


load_dotenv()

def calculate_tokens_receive(sol_amount, previous_sol=30, slippage=25):
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

def load_keypair_from_private_key(self, private_key_str):
    """Load keypair from private key string."""
    try:
        private_key_bytes = base58.b58decode(private_key_str)
        return Keypair.from_bytes(private_key_bytes)
    except Exception as e:
        raise Exception(f"Failed to load keypair: {str(e)}")

async def get_inx_transfer(amount_sol, sender_pubkey, receiver_pubkey):
    amount = int(amount_sol * 1e9)
    transfer_ix = transfer(
        TransferParams(
            from_pubkey=sender_pubkey,
            to_pubkey=receiver_pubkey,
            lamports=amount
        )
    )
    return transfer_ix


async def get_inx_set_compute_unit_price(unit_price):
    set_compute_unit_price_ix = set_compute_unit_price(unit_price)
    return set_compute_unit_price_ix

async def get_inx_extend_account(account,mint,program_id):

    discriminator  = f"global:extend_account".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    extend_account_layout = CStruct()
    instruction_data = discriminator_hash + extend_account_layout.build({})

    seed_curve = [b"bonding-curve", bytes(mint.pubkey())]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    event_authority = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

    #create associated token account

    accounts = [
        AccountMeta(curve_pda, False, True),
        AccountMeta(account.pubkey(), True, True),
        AccountMeta(_ID, False, False),
        AccountMeta(event_authority, False, False),
        AccountMeta(program_id, False, False),
    ]

    ix = Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    )
    return ix

async def get_inx_create_associated_token_account(mint, payer):

    ix = create_idempotent_associated_token_account(payer.pubkey(), payer.pubkey(), mint.pubkey())

    return ix

async def get_inx_create_pump_fun(client,program_id, payer,creator_pubkey):
    discriminator  = f"global:create".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    create_token_layout = CStruct(
        "name" / String,
        "symbol" / String,
        "uri" / String,
        "creator" / BorshPubkey,
    )
    
    # Convert pubkey to proper byte array
    creator_bytes = bytes(creator_pubkey)
    print(creator_bytes, "*****")
    
    instruction_data = discriminator_hash + create_token_layout.build(
        {
            "name": "Pump Fun V2", 
            "symbol": "PUMP", 
            "uri": "https://pumpfun.io", 
            "creator": creator_pubkey  # Use the properly converted bytes
        }
    )

    token_mint_authority = Pubkey.from_string("TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM")

    #create mint
    mint_keypair = Keypair()

    seed_curve = [b"bonding-curve", bytes(mint_keypair.pubkey())]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    vault_pda = get_associated_token_address( curve_pda,mint_keypair.pubkey())
    METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
    seed_metadata = [b"metadata", bytes(METADATA_PROGRAM_ID),bytes(mint_keypair.pubkey())]
    token_metadata_pda, _ = Pubkey.find_program_address(seed_metadata, METADATA_PROGRAM_ID)
    config = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
    associated_token_program = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    rent_program = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
    event_authority = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")


    
    # Get payer's associated token account

    accounts = [
        AccountMeta(mint_keypair.pubkey(), True, True),  # Mint
        AccountMeta(token_mint_authority, False, False),  # Mint Authority
        AccountMeta(curve_pda, False, True),  # Curve
        AccountMeta(vault_pda, False, True),  # Vault
        AccountMeta(config, False, False),  # Config,
        AccountMeta(METADATA_PROGRAM_ID, False, False),
        AccountMeta(token_metadata_pda, False, True),  # Token Metadata  
        AccountMeta(payer.pubkey(), True, True),  # payer     
        AccountMeta(_ID, False, False),
        AccountMeta(_TOKEN_PROGRAM_ID, False, False),
        AccountMeta(associated_token_program, False, False),
        AccountMeta(rent_program, False, False),
        AccountMeta(event_authority, False, False),
        AccountMeta(program_id, False, False),
    ]


    ix = Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    )
    return ix, mint_keypair

async def get_inx_buy_token_dev(program_id,buyer,mint,buy_args, creator_pubkey):
    discriminator  = f"global:buy".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    buy_token_layout = CStruct(
        "amount" / U64,
        "max_sol_cost" / U64,
    )
    instruction_data = discriminator_hash + buy_token_layout.build(buy_args)

    seed_curve = [b"bonding-curve", bytes(mint.pubkey())]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    
    # Find creator vault using the creator from token creation
    creator_vault_pda, _ = Pubkey.find_program_address(
        [b"creator-vault", bytes(creator_pubkey)], program_id)

    vault_pda = get_associated_token_address(curve_pda, mint.pubkey())
    associated_user_ata = get_associated_token_address(buyer.pubkey(), mint.pubkey())
    config = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
    event_authority = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

    accounts = [
        AccountMeta(config, False, False),  # Config
        AccountMeta(Pubkey.from_string("68yFSZxzLWJXkxxRGydZ63C6mHx1NLEDWmwN9Lb5yySg"), False, True),  # Buyer
        AccountMeta(mint.pubkey(), False, True),  # Mint
        AccountMeta(curve_pda, False, True),  # Vault
        AccountMeta(vault_pda, False, True),  # User ATA
        AccountMeta(associated_user_ata, False, True),
        AccountMeta(buyer.pubkey(), True, True),
        AccountMeta(_ID, False, False),
        AccountMeta(_TOKEN_PROGRAM_ID, False, False),
        AccountMeta(creator_vault_pda, False, True),
        AccountMeta(event_authority, False, False),
        AccountMeta(program_id, False, False),
    ]

    ix = Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    )
    return ix

async def get_inx_buy_token(program_id,buyer,mint,buy_args, creator_pubkey):
    discriminator  = f"global:buy".encode("utf-8")
    discriminator_hash = hashlib.sha256(discriminator).digest()[:8]
    buy_token_layout = CStruct(
        "amount" / U64,
        "max_sol_cost" / U64,
    )
    instruction_data = discriminator_hash + buy_token_layout.build(buy_args)

    
    
    # Find creator vault using the creator from token creation
    creator_vault_pda, _ = Pubkey.find_program_address(
        [b"creator-vault", bytes(creator_pubkey)], program_id)
    seed_curve = [b"bonding-curve", bytes(mint)]
    curve_pda, _ = Pubkey.find_program_address(seed_curve, program_id)
    vault_pda = get_associated_token_address(curve_pda, mint)
    associated_user_ata = get_associated_token_address(buyer.pubkey(), mint)
    config = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
    event_authority = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")

    accounts = [
        AccountMeta(config, False, False),  # Config
        AccountMeta(Pubkey.from_string("68yFSZxzLWJXkxxRGydZ63C6mHx1NLEDWmwN9Lb5yySg"), False, True),  # Buyer
        AccountMeta(mint, False, True),  # Mint
        AccountMeta(curve_pda, False, True),  # Vault
        AccountMeta(vault_pda, False, True),  # User ATA
        AccountMeta(associated_user_ata, False, True),
        AccountMeta(buyer.pubkey(), True, True),
        AccountMeta(_ID, False, False),
        AccountMeta(_TOKEN_PROGRAM_ID, False, False),
        AccountMeta(creator_vault_pda, False, True),
        AccountMeta(event_authority, False, False),
        AccountMeta(program_id, False, False),
    ]

    ix = Instruction(
        program_id=program_id,
        accounts=accounts,
        data=instruction_data
    )
    return ix

async def get_tx(ixs, signers, recent_blockhash):
    tx = Transaction(
        from_keypairs=signers,
        message=Message.new_with_blockhash(ixs, signers[0].pubkey(), recent_blockhash),
        recent_blockhash=recent_blockhash
    )
    return tx

async def main():
    client = AsyncClient("https://api.devnet.solana.com")

    YOUR_PRIVATE_KEY = (os.getenv("account_a_pk")).split(",")
    YOUR_PRIVATE_KEY = [int(byte) for byte in YOUR_PRIVATE_KEY]
    private_key_bytes = bytes(YOUR_PRIVATE_KEY)
    private_key_str = base58.b58encode(private_key_bytes).decode('ascii')
    account_a = load_keypair_from_private_key(client, private_key_str)
    print(f"Account A public key: {account_a.pubkey()}")

    YOUR_PRIVATE_KEY_2 = (os.getenv("account_b_pk")).split(",")
    YOUR_PRIVATE_KEY_2 = [int(byte) for byte in YOUR_PRIVATE_KEY_2]
    private_key_bytes_2 = bytes(YOUR_PRIVATE_KEY_2)
    private_key_str_2 = base58.b58encode(private_key_bytes_2).decode('ascii')
    account_b = load_keypair_from_private_key(client, private_key_str_2)
    print(f"Account B public key: {account_b.pubkey()}")

    program_id = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")

    # Verify program account exists
    program_info = await client.get_account_info(program_id)
    if not program_info.value:
        raise Exception(f"Program account {program_id} not found")

    recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
    ix_compute_budget = await get_inx_set_compute_unit_price(1000000000)

    # Create PumpFun token
    creator_pubkey = account_a.pubkey()
    ix_create_pump_fun, mint_keypair = await get_inx_create_pump_fun(
        client,
        program_id, 
        account_a,
        creator_pubkey
    )
    # buy_args = calculate_tokens_receive(0.0001)

    # #create extend account
    # ix_extend_account = await get_inx_extend_account(
    #     account_a,
    #     mint_keypair,
    #     program_id
    # )

    #create associated token account
    ix_create_associated_token_account = await get_inx_create_associated_token_account(
        mint_keypair,
        account_a,
    )

    #create associated token account
    ix_create_associated_token_account_2 = await get_inx_create_associated_token_account(
        mint_keypair,
        account_b,
    )

    # Buy token dev
    ix_buy_token_dev = await get_inx_buy_token_dev(
        program_id,
        account_a,
        mint_keypair,
        calculate_tokens_receive(0.0001),
        creator_pubkey
    )

    #buy token
    ix_buy_token = await get_inx_buy_token(
        program_id,
        account_b,
        mint_keypair.pubkey(),
        calculate_tokens_receive(0.0002),
        creator_pubkey
    )

    # Build transaction
    ixs = [ix_create_pump_fun, ix_create_associated_token_account, ix_buy_token_dev, ix_create_associated_token_account_2, ix_buy_token]
    tx = await get_tx(ixs, [account_a,account_b,mint_keypair], recent_blockhash)
    sim_result = await client.send_transaction(tx, opts=TxOpts(skip_preflight=False))
    print(f"sim_result: {sim_result}")


if __name__ == "__main__":
    asyncio.run(main())
