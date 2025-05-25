from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import (TransferParams, transfer ,create_lookup_table,
    extend_lookup_table,
    freeze_lookup_table,
    deactivate_lookup_table,
    close_lookup_table,
    CreateLookupTableParams,
    ExtendLookupTableParams,
    FreezeLookupTableParams,
    DeactivateLookupTableParams,
    CloseLookupTableParams,
)

from solders.transaction import Transaction, VersionedTransaction
from solana.rpc.async_api import AsyncClient
import asyncio
import base58
import base64
import os
from dotenv import load_dotenv
from typing import List, Tuple, Optional
from solders.message import Message, MessageV0
from solders.address_lookup_table_account import (
    AddressLookupTableAccount,
    AddressLookupTable,
    derive_lookup_table_address
)

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

    async def create_address_lookup_table(self, authority: Keypair, payer: Keypair, recent_blockhash: bytes) -> Tuple[Pubkey, str]:
        """
        Create a new Address Lookup Table.
        
        Args:
            authority: The authority keypair that can modify the lookup table
            payer: The keypair that will pay for the transaction
            recent_blockhash: The recent blockhash for the transaction
            
        Returns:
            Tuple of (lookup_table_address, transaction_signature)
        """
        try:
            # Create lookup table instruction
            lookup_table_address = Pubkey.new_unique()
            create_lookup_table_ix = create_lookup_table(
                CreateLookupTableParams(
                    authority=authority.pubkey(),
                    payer=payer.pubkey(),
                    recent_slot=recent_blockhash
                )
            )
            
            # Create transaction
            transaction = Transaction()
            transaction.add(create_lookup_table_ix)
            transaction.recent_blockhash = recent_blockhash
            
            # Sign transaction
            transaction.sign([payer])
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return lookup_table_address, result.value
            
        except Exception as e:
            raise Exception(f"Failed to create address lookup table: {str(e)}")

    async def extend_address_lookup_table(self, lookup_table_address: Pubkey, authority: Keypair, addresses: List[Pubkey]) -> str:
        """
        Extend an existing Address Lookup Table with new addresses.
        
        Args:
            lookup_table_address: The address of the lookup table to extend
            authority: The authority keypair that can modify the lookup table
            addresses: List of addresses to add to the lookup table
            
        Returns:
            Transaction signature
        """
        try:
            # Get recent blockhash
            recent_blockhash = await self.client.get_latest_blockhash()
            
            # Create extend lookup table instruction
            extend_lookup_table_ix = extend_lookup_table(
                ExtendLookupTableParams(
                    lookup_table=lookup_table_address,
                    authority=authority.pubkey(),
                    payer=authority.pubkey(),
                    addresses=addresses
                )
            )
            
            # Create transaction
            transaction = Transaction()
            transaction.add(extend_lookup_table_ix)
            transaction.recent_blockhash = recent_blockhash.value.blockhash
            
            # Sign transaction
            transaction.sign([authority])
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value
            
        except Exception as e:
            raise Exception(f"Failed to extend address lookup table: {str(e)}")

    async def create_and_extend_lookup_table(self, authority: Keypair, addresses: List[Pubkey]) -> Tuple[Pubkey, Pubkey, str]:
        """
        Create and extend an Address Lookup Table in a single transaction.
        
        Args:
            authority: The authority keypair that can modify the lookup table
            addresses: List of addresses to add to the lookup table
            
        Returns:
            Tuple of (lookup_table_address, transaction_signature)
        """
        try:
            # Get recent blockhash
            recent_blockhash = await self.client.get_latest_blockhash()
            slot = await self.client.get_slot()
            
            # Create lookup table address
            
            # Create lookup table instruction
            create_ix, lut_address = create_lookup_table(
                CreateLookupTableParams(
                    authority_address=authority.pubkey(),
                    payer_address=authority.pubkey(),
                    recent_slot=slot.value - 1
                )
            )
            
            # Create extend lookup table instruction
            extend_lookup_table_ix = extend_lookup_table(
                ExtendLookupTableParams(
                    lookup_table_address=lut_address,
                    authority_address=authority.pubkey(),
                    payer_address=authority.pubkey(),
                    new_addresses=addresses
                )
            )
            
            # Create transaction with both instructions
            message = MessageV0.try_compile(
                    payer=authority.pubkey(),
                    instructions=[create_ix, extend_lookup_table_ix],
                    address_lookup_table_accounts=[],
                    recent_blockhash=recent_blockhash.value.blockhash
            )
            tx = VersionedTransaction(message, [authority])

            lut_account = AddressLookupTableAccount(
                key=lut_address,
                addresses=addresses
            )

            tx_sig = await self.client.send_transaction(tx)

            return lut_address, lut_account, tx
            
        except Exception as e:
            raise Exception(f"Failed to create and extend address lookup table: {str(e)}")

    async def batch_transfer_sol_v2(self, from_keypair: Keypair,recipients: List[Tuple[Pubkey, float]], lookup_table_account: AddressLookupTableAccount) -> str:
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

            # Create message v0
            message = MessageV0.try_compile(
                from_keypair.pubkey(),
                transfer_instructions,
                [lookup_table_account],  # Use the lookup table
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

    async def batch_collect_sol_v2(self, collector_keypair: Keypair, senders: List[Tuple[Keypair, float]], lookup_table_account: AddressLookupTableAccount) -> str:
        """
        Create and send a versioned transaction to collect SOL from multiple accounts using an Address Lookup Table.
        
        Args:
            collector_keypair: The collector's keypair (recipient)
            senders: List of tuples containing (sender_keypair, amount_sol)
            lookup_table_account: The Address Lookup Table account containing all addresses
            
        Returns:
            Transaction signature
        """
        try:
            # Get recent blockhash first
            recent_blockhash = await self.client.get_latest_blockhash()
            
            # Create transfer instructions
            transfer_instructions = []
            for sender_keypair, amount_sol in senders:
                amount_lamports = int(amount_sol * 1e9)
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=sender_keypair.pubkey(),
                        to_pubkey=collector_keypair.pubkey(),
                        lamports=amount_lamports
                    )
                )
                transfer_instructions.append(transfer_ix)
            #payer is the first sender
            payer = senders[0][0]
            # Create message v0
            message = MessageV0.try_compile(
                payer.pubkey(),  # payer
                transfer_instructions,
                [lookup_table_account],  # Use the lookup table
                recent_blockhash.value.blockhash,
            )
            
            # Create versioned transaction
            # Get all signers (collector and all senders)
            all_signers = [sender_keypair for sender_keypair, _ in senders]
            transaction = VersionedTransaction(
                message,
                all_signers  # All signers need to sign
            )

            print(f"tx bytes: {len(bytes(transaction))}")
            
            # Send transaction
            result = await self.client.send_transaction(transaction)
            return result.value
            
        except Exception as e:
            raise Exception(f"Batch collection v2 failed: {str(e)}")

    async def close(self):
        """Close the client connection."""
        await self.client.close()

    async def is_lookup_table_available(self, lookup_table_address: Pubkey) -> bool:
        """
        Check if an Address Lookup Table is available.
        
        Args:
            lookup_table_address: The address of the lookup table to check
            
        Returns:
            bool: True if the lookup table exists and is available, False otherwise
        """
        try:
            # Get account info
            account_info = await self.client.get_account_info(lookup_table_address)

            print(f"Account info: {account_info}")
            
            if not account_info.value:
                return False
                
            # Check if the account is owned by the Address Lookup Table program
            # The Address Lookup Table program ID is "AddressLookupTab1e1111111111111111111111111"
            lookup_table_program_id = Pubkey.from_string("AddressLookupTab1e1111111111111111111111111")
            
            return account_info.value.owner == lookup_table_program_id
            
        except Exception as e:
            raise Exception(f"Failed to check lookup table availability: {str(e)}")

    async def get_lookup_table_data(self, lookup_table_address: Pubkey) -> Optional[AddressLookupTableAccount]:
        """
        Get AddressLookupTableAccount information by its pubkey.
        
        Args:
            lookup_table_address: The address of the lookup table to check
            
        Returns:
            Optional[AddressLookupTableAccount]: The parsed lookup table account if found and valid, None otherwise
        """
        try:
            print(f"\nFetching lookup table data for address: {lookup_table_address}")
            
            # Get account info
            account_info = await self.client.get_account_info(lookup_table_address)
            print(f"Account info response: {account_info}")
            
            if not account_info.value:
                print("Lookup table does not exist")
                return None
            
            # Check if the account is owned by the Address Lookup Table program
            lookup_table_program_id = Pubkey.from_string("AddressLookupTab1e1111111111111111111111111")
            if account_info.value.owner != lookup_table_program_id:
                print(f"Account is not owned by Address Lookup Table program. Owner: {account_info.value.owner}")
                return None

            # Validate account data
            if not account_info.value.data:
                print("Account data is empty")
                return None

            try:
                # Try to decode base64 data first
                
                # Parse using AddressLookupTable first
                lookup_table = AddressLookupTable.deserialize(account_info.value.data)
                print(f"Successfully parsed lookup table with {len(lookup_table.addresses)} addresses")
                
                # Convert to AddressLookupTableAccount
                account = AddressLookupTableAccount(
                    key=lookup_table_address,
                    addresses=lookup_table.addresses
                )
                
                return account
                
            except Exception as parse_error:
                print(f"Failed to parse lookup table data: {str(parse_error)}")
                print(f"Raw data (first 100 chars): {account_info.value.data[:100]}")
                return None
            
        except Exception as e:
            print(f"Failed to get lookup table data: {str(e)}")
            return None

async def main():
    # Initialize transfer client
    transfer_client = SolanaTransfer()

    try:
        # Load your account from private key (Account A)
        #convert the private key to a list of bytes (having errors with the private key as a string)
        YOUR_PRIVATE_KEY = (os.getenv("account_a_pk")).split(",")
        YOUR_PRIVATE_KEY = [int(byte) for byte in YOUR_PRIVATE_KEY]
        private_key_bytes = bytes(YOUR_PRIVATE_KEY)
        private_key_str = base58.b58encode(private_key_bytes).decode('ascii')
        account_a = transfer_client.load_keypair_from_private_key(private_key_str)
        print(f"Account A public key: {account_a.pubkey()}")

        # Load your account from private key (Account B)
        YOUR_PRIVATE_KEY_B = (os.getenv("account_b_pk")).split(",")
        YOUR_PRIVATE_KEY_B = [int(byte) for byte in YOUR_PRIVATE_KEY_B]
        private_key_bytes_b = bytes(YOUR_PRIVATE_KEY_B)
        private_key_str_b = base58.b58encode(private_key_bytes_b).decode('ascii')
        account_b = transfer_client.load_keypair_from_private_key(private_key_str_b)
        print(f"Account B public key: {account_b.pubkey()}")

        # Load your account from private key (Account C)
        YOUR_PRIVATE_KEY_C = (os.getenv("account_c_pk")).split(",")
        YOUR_PRIVATE_KEY_C = [int(byte) for byte in YOUR_PRIVATE_KEY_C]
        private_key_bytes_c = bytes(YOUR_PRIVATE_KEY_C)
        private_key_str_c = base58.b58encode(private_key_bytes_c).decode('ascii')
        account_c = transfer_client.load_keypair_from_private_key(private_key_str_c)
        print(f"Account C public key: {account_c.pubkey()}")

        #load your account from private key (Account D)
        YOUR_PRIVATE_KEY_D = (os.getenv("account_d_pk")).split(",")
        YOUR_PRIVATE_KEY_D = [int(byte) for byte in YOUR_PRIVATE_KEY_D]
        private_key_bytes_d = bytes(YOUR_PRIVATE_KEY_D)
        private_key_str_d = base58.b58encode(private_key_bytes_d).decode('ascii')
        account_d = transfer_client.load_keypair_from_private_key(private_key_str_d)
        print(f"Account D public key: {account_d.pubkey()}")

        # Get initial balances
        print("\n=== Initial Balances ===")
        balance_a = await transfer_client.get_balance(account_a.pubkey())
        balance_b = await transfer_client.get_balance(account_b.pubkey())
        balance_c = await transfer_client.get_balance(account_c.pubkey())
        balance_d = await transfer_client.get_balance(account_d.pubkey())
        print(f"Account A balance: {balance_a} SOL")
        print(f"Account B balance: {balance_b} SOL")
        print(f"Account C balance: {balance_c} SOL")
        print(f"Account D balance: {balance_d} SOL")

        # use a ALT to transfer SOL from A to B, C, and D
        lut_address = Pubkey.from_string("AXitaTHCCsSkGKCKQB9g2TEQgDdqWGR3Pk2EQK5tsTov")
        lut_account = await transfer_client.get_lookup_table_data(lut_address)
        print(f"Lookup table address: {lut_address}")
        print(f"Lookup table account: {lut_account}")

        # Batch collect SOL from B, C, and D back to A using versioned transaction
        print("\n=== Batch Collection V2 Example ===")
        collection_amounts = [
            (account_b, 0.01),  # Collect 0.01 SOL from B
            (account_c, 0.01),  # Collect 0.01 SOL from C
            (account_d, 0.01)   # Collect 0.01 SOL from D
        ]
        print(f"Collecting 0.01 SOL from each of B, C, and D back to A...")
        collection_signature = await transfer_client.batch_collect_sol_v2(account_a, collection_amounts, lut_account)
        print(f"Batch collection v2 signature: {collection_signature}")

        # Print final balances
        print("\n=== Final Balances ===")
        balance_a = await transfer_client.get_balance(account_a.pubkey())
        balance_b = await transfer_client.get_balance(account_b.pubkey())
        balance_c = await transfer_client.get_balance(account_c.pubkey())
        balance_d = await transfer_client.get_balance(account_d.pubkey())
        print(f"Account A balance: {balance_a} SOL")
        print(f"Account B balance: {balance_b} SOL")
        print(f"Account C balance: {balance_c} SOL")
        print(f"Account D balance: {balance_d} SOL")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await transfer_client.close()

async def main_v2():
    transfer_client = SolanaTransfer()

    YOUR_PRIVATE_KEY = (os.getenv("account_a_pk")).split(",")
    YOUR_PRIVATE_KEY = [int(byte) for byte in YOUR_PRIVATE_KEY]
    private_key_bytes = bytes(YOUR_PRIVATE_KEY)
    private_key_str = base58.b58encode(private_key_bytes).decode('ascii')
    account_a = transfer_client.load_keypair_from_private_key(private_key_str)
    print(f"Account A public key: {account_a.pubkey()}")

    # Load your account from private key (Account B)
    YOUR_PRIVATE_KEY_B = (os.getenv("account_b_pk")).split(",")
    YOUR_PRIVATE_KEY_B = [int(byte) for byte in YOUR_PRIVATE_KEY_B]
    private_key_bytes_b = bytes(YOUR_PRIVATE_KEY_B)
    private_key_str_b = base58.b58encode(private_key_bytes_b).decode('ascii')
    account_b = transfer_client.load_keypair_from_private_key(private_key_str_b)
    print(f"Account B public key: {account_b.pubkey()}")

    # Load your account from private key (Account C)
    YOUR_PRIVATE_KEY_C = (os.getenv("account_c_pk")).split(",")
    YOUR_PRIVATE_KEY_C = [int(byte) for byte in YOUR_PRIVATE_KEY_C]
    private_key_bytes_c = bytes(YOUR_PRIVATE_KEY_C)
    private_key_str_c = base58.b58encode(private_key_bytes_c).decode('ascii')
    account_c = transfer_client.load_keypair_from_private_key(private_key_str_c)
    print(f"Account C public key: {account_c.pubkey()}")

    #load your account from private key (Account D)
    YOUR_PRIVATE_KEY_D = (os.getenv("account_d_pk")).split(",")
    YOUR_PRIVATE_KEY_D = [int(byte) for byte in YOUR_PRIVATE_KEY_D]
    private_key_bytes_d = bytes(YOUR_PRIVATE_KEY_D)
    private_key_str_d = base58.b58encode(private_key_bytes_d).decode('ascii')
    account_d = transfer_client.load_keypair_from_private_key(private_key_str_d)
    print(f"Account D public key: {account_d.pubkey()}")

    #create and extend lookup table
    lut_address, lut_account, tx = await transfer_client.create_and_extend_lookup_table(
        account_a,
        [account_b.pubkey(), account_c.pubkey(),account_d.pubkey()]
    )
    print(f"Lookup table address: {lut_address}")
    print(f"Lookup table account: {lut_account}")
    
    

if __name__ == "__main__":
    asyncio.run(main()) 