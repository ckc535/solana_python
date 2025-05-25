from solana.rpc.async_api import AsyncClient
import os
from dotenv import load_dotenv
from typing import Optional

class SolanaAsyncClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SolanaAsyncClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the client with RPC URL from environment variables."""
        load_dotenv()
        self.rpc_url = os.getenv("RPC_URL", "https://api.devnet.solana.com")
        self._client = AsyncClient(self.rpc_url)

    @property
    def client(self) -> AsyncClient:
        """Get the AsyncClient instance."""
        return self._client

    async def close(self):
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._instance = None

    @classmethod
    async def get_client(cls) -> AsyncClient:
        """Get or create a client instance."""
        if cls._instance is None:
            cls()
        return cls._instance.client

    @classmethod
    async def close_client(cls):
        """Close the client connection."""
        if cls._instance:
            await cls._instance.close() 