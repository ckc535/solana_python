from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction, VersionedTransaction
from solana.rpc.async_api import AsyncClient
import asyncio
import base58
import os
from dotenv import load_dotenv
from typing import List, Tuple
from solders.message import Message, MessageV0
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.instruction import AccountMeta, create_address_lookup_table, extend_lookup_table

# Load environment variables
load_dotenv()

class SolanaTransfer:
    def __init__(self, rpc_url=None):
        """Initialize SolanaTransfer with RPC URL."""
        self.rpc_url = rpc_url or os.getenv("RPC_URL", "https://api.testnet.solana.com")
        self.client = AsyncClient(self.rpc_url)

    async def create_account(self):
        """Create a new Solana account."""
        return Keypair()

    def load_keypair_from_private_key(self, private_key_str):
        """Load keypair from private key string."""
        try:
            private_key_bytes = base58.b58decode(private_key_str)
            return Keypair.from_bytes(private_key_bytes)
        except Exception as e:
            raise Exception(f"Failed to load keypair: {str(e)}")

    async def get_balance(self, pubkey):
        """Get SOL balance for an account."""
        try:
            response = await self.client.get_balance(pubkey)
            return response.value / 1e9  # Convert lamports to SOL
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")

    async def transfer_sol(self, from_keypair, to_pubkey, amount_sol):
        """Transfer SOL from one account to another."""
        try:
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1e9)

            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_keypair.pubkey(),
                    to_pubkey=Pubkey.from_string(to_pubkey),
                    lamports=amount_lamports
                )
            )

            # Create and sign transaction
            transaction = Transaction()
            transaction.add(transfer_ix)
            
            # Get recent blockhash
            recent_blockhash = await self.client.get_latest_blockhash()
            transaction.recent_blockhash = recent_blockhash.value.blockhash

            # Sign transaction
            transaction.sign([from_keypair])

            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value

        except Exception as e:
            raise Exception(f"Transfer failed: {str(e)}")

    async def batch_transfer_sol(self, from_keypair: Keypair, recipients: List[Tuple[Pubkey, float]]) -> str:
        """
        Create and send a transaction with multiple transfer instructions.
        
        Args:
            from_keypair: The sender's keypair
            recipients: List of tuples containing (recipient_pubkey, amount_sol)
        
        Returns:
            Transaction signature
        """
        try:
            # Get recent blockhash first
            recent_blockhash = await self.client.get_latest_blockhash()
            
            # Create transfer instructions
            instructions = []
            for recipient_pubkey, amount_sol in recipients:
                amount_lamports = int(amount_sol * 1e9)
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=from_keypair.pubkey(),
                        to_pubkey=recipient_pubkey,
                        lamports=amount_lamports
                    )
                )
                instructions.append(transfer_ix)


            
            # Create message
            message = Message.new_with_blockhash(
                instructions,
                from_keypair.pubkey(),
                recent_blockhash.value.blockhash
            )
            
            # Create transaction with required parameters
            transaction = Transaction(
                from_keypairs=[from_keypair],
                message=message,
                recent_blockhash=recent_blockhash.value.blockhash
            )

            print(f"tx bytest: {len(bytes(transaction))}")
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value
            
        except Exception as e:
            raise Exception(f"Batch transfer failed: {str(e)}")

    async def batch_collect_sol(self, collector_keypair: Keypair, senders: List[Tuple[Keypair, float]]) -> str:
        """
        Create and send a transaction to collect SOL from multiple accounts.
        
        Args:
            collector_keypair: The collector's keypair (recipient)
            senders: List of tuples containing (sender_keypair, amount_sol)
        
        Returns:
            Transaction signature
        """
        try:
            # Get recent blockhash first
            recent_blockhash = await self.client.get_latest_blockhash()
            
            # Create transfer instructions
            instructions = []
            for sender_keypair, amount_sol in senders:
                amount_lamports = int(amount_sol * 1e9)
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=sender_keypair.pubkey(),
                        to_pubkey=collector_keypair.pubkey(),
                        lamports=amount_lamports
                    )
                )
                instructions.append(transfer_ix)
            
            # Create message
            # Get pubkeys of all the sender keypairs (not the tuples)
            sender_pubkeys = [sender_keypair.pubkey() for sender_keypair, _ in senders]
            message = Message.new_with_blockhash(
                instructions,
                sender_pubkeys[0],
                recent_blockhash.value.blockhash
            )
            
            # Create transaction with required parameters
            # Get the keypairs from the tuples
            all_signers = [sender_keypair for sender_keypair, _ in senders]
            transaction = Transaction(
                from_keypairs=all_signers,  # All signers need to sign
                message=message,
                recent_blockhash=recent_blockhash.value.blockhash
            )
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value
            
        except Exception as e:
            raise Exception(f"Batch collection failed: {str(e)}")

    async def batch_transfer_sol_v2(self, from_keypair: Keypair, recipients: List[Tuple[Pubkey, float]]) -> str:
        """
        Create and send a versioned transaction that creates an address lookup table and performs transfers in one tx.
        """
        try:
            # Get recent blockhash first
            recent_blockhash = await self.client.get_latest_blockhash()
            
            # Create list of all unique pubkeys
            all_pubkeys = set()
            all_pubkeys.add(from_keypair.pubkey())
            for recipient_pubkey, _ in recipients:
                all_pubkeys.add(recipient_pubkey)
            
            # Create lookup table instruction
            lookup_table_address = Pubkey.new_unique()
            create_lookup_table_ix = create_address_lookup_table(
                from_keypair.pubkey(),
                from_keypair.pubkey(),
                recent_blockhash.value.blockhash
            )
            
            # Create extend lookup table instruction
            extend_lookup_table_ix = extend_lookup_table(
                lookup_table_address,
                from_keypair.pubkey(),
                list(all_pubkeys)
            )
            
            # Create transfer instructions
            transfer_instructions = []
            for recipient_pubkey, amount_sol in recipients:
                amount_lamports = int(amount_sol * 1e9)
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=from_keypair.pubkey(),
                        to_pubkey=recipient_pubkey,
                        lamports=amount_lamports
                    )
                )
                transfer_instructions.append(transfer_ix)

            # Combine all instructions
            all_instructions = [create_lookup_table_ix, extend_lookup_table_ix] + transfer_instructions

            # Create message v0
            message = MessageV0.try_compile(
                from_keypair.pubkey(),
                all_instructions,
                [],  # No lookup tables needed since we're creating it in this tx
                recent_blockhash.value.blockhash,
            )
            
            # Create versioned transaction
            transaction = VersionedTransaction(
                message,
                [from_keypair]  # Signers
            )

            print(f"tx bytes: {len(bytes(transaction))}")
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value
            
        except Exception as e:
            raise Exception(f"Batch transfer v2 failed: {str(e)}")

    async def close(self):
        """Close the client connection."""
        await self.client.close()

async def main():
    # Initialize transfer client
    transfer_client = SolanaTransfer()

    try:
        # Load your account from private key (Account A)
        YOUR_PRIVATE_KEY = [68,126,90,68,29,160,132,242,79,115,130,250,44,31,13,240,245,116,48,234,184,1,231,75,127,76,199,122,181,154,188,90,45,121,113,121,195,212,219,239,16,108,210,8,211,52,127,107,109,102,185,252,144,112,113,238,28,186,158,34,214,146,46,93]
        private_key_bytes = bytes(YOUR_PRIVATE_KEY)
        private_key_str = base58.b58encode(private_key_bytes).decode('ascii')
        account_a = transfer_client.load_keypair_from_private_key(private_key_str)
        print(f"Account A public key: {account_a.pubkey()}")

        # Load your account from private key (Account B)
        YOUR_PRIVATE_KEY_B = [115,161,159,149,255,254,214,238,112,241,171,133,24,21,150,17,227,90,136,164,6,39,16,155,118,30,155,177,49,176,208,181,160,207,232,62,98,190,250,191,68,2,140,155,101,253,30,140,183,202,127,138,221,225,157,104,44,99,239,101,236,220,157,59]
        private_key_bytes_b = bytes(YOUR_PRIVATE_KEY_B)
        private_key_str_b = base58.b58encode(private_key_bytes_b).decode('ascii')
        account_b = transfer_client.load_keypair_from_private_key(private_key_str_b)
        print(f"Account B public key: {account_b.pubkey()}")

        # Load your account from private key (Account C)
        YOUR_PRIVATE_KEY_C = [73,204,123,204,167,157,181,51,175,151,79,55,18,47,249,144,176,180,147,172,14,76,82,157,100,196,28,86,250,48,163,68,99,120,198,174,194,209,195,149,238,229,55,208,92,196,69,0,219,10,140,185,164,72,160,57,33,174,215,74,17,168,10,51]
        private_key_bytes_c = bytes(YOUR_PRIVATE_KEY_C)
        private_key_str_c = base58.b58encode(private_key_bytes_c).decode('ascii')
        account_c = transfer_client.load_keypair_from_private_key(private_key_str_c)
        print(f"Account C public key: {account_c.pubkey()}")
        
        # Get initial balances
        print("\n=== Initial Balances ===")
        balance_a = await transfer_client.get_balance(account_a.pubkey())
        balance_b = await transfer_client.get_balance(account_b.pubkey())
        balance_c = await transfer_client.get_balance(account_c.pubkey())
        print(f"Account A balance: {balance_a} SOL")
        print(f"Account B balance: {balance_b} SOL")
        print(f"Account C balance: {balance_c} SOL")
        

        # Batch transfer SOL from A to B and C using versioned transaction
        print("\n=== Batch Transfer V2 Example ===")
        transfer_amount = 0.01  # Amount to transfer in SOL
        list_transfer = [
            (account_b.pubkey(), transfer_amount), 
            (account_c.pubkey(), transfer_amount),
        ]
        transfer_signature = await transfer_client.batch_transfer_sol_v2(
            account_a,
            list_transfer
        )
        print(f"Batch transfer v2 signature: {transfer_signature}")

        # Batch collect SOL from B and C back to A
        print("\n=== Batch Collection Example ===")
        # Create a list of tuples with (sender_keypair, amount)
        collection_amounts = [
            (account_b, 0.01),  # Collect 0.01 SOL from B
            (account_c, 0.01)   # Collect 0.01 SOL from C
        ]
        print(f"Collecting 0.01 SOL from each of B and C back to A...")
        # collection_signature = await transfer_client.batch_collect_sol(account_a, collection_amounts)
        # print(f"Batch collection signature: {collection_signature}")

        # Print final balances
        print("\n=== Final Balances ===")
        balance_a = await transfer_client.get_balance(account_a.pubkey())
        balance_b = await transfer_client.get_balance(account_b.pubkey())
        balance_c = await transfer_client.get_balance(account_c.pubkey())
        print(f"Account A balance: {balance_a} SOL")
        print(f"Account B balance: {balance_b} SOL")
        print(f"Account C balance: {balance_c} SOL")

    

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await transfer_client.close()

if __name__ == "__main__":
    asyncio.run(main()) 