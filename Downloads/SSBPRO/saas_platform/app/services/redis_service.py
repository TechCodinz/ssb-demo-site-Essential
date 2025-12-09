"""
Sol Sniper Bot PRO - Redis Service
Pub/Sub for live logs and worker commands
"""
import asyncio
import json
from typing import Optional, Callable
import redis.asyncio as redis

from app.core.config import settings


class RedisService:
    """Redis service for pub/sub messaging"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub = None
    
    async def connect(self):
        """Connect to Redis"""
        if not self._client:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def publish_log(self, bot_id: str, data: dict):
        """Publish a log message for a bot"""
        client = await self.connect()
        channel = f"logs:{bot_id}"
        await client.publish(channel, json.dumps(data))
    
    async def publish_command(self, user_id: str, command: dict):
        """Publish a command for a worker"""
        client = await self.connect()
        channel = f"commands:{user_id}"
        await client.publish(channel, json.dumps(command))
    
    async def subscribe_logs(self, bot_id: str, callback: Callable):
        """Subscribe to log messages for a bot"""
        client = await self.connect()
        pubsub = client.pubsub()
        channel = f"logs:{bot_id}"
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)
    
    async def subscribe_commands(self, user_id: str, callback: Callable):
        """Subscribe to commands for a worker"""
        client = await self.connect()
        pubsub = client.pubsub()
        channel = f"commands:{user_id}"
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)
    
    async def set_state(self, key: str, value: dict, expire: int = 3600):
        """Set state in Redis with expiry"""
        client = await self.connect()
        await client.setex(key, expire, json.dumps(value))
    
    async def get_state(self, key: str) -> Optional[dict]:
        """Get state from Redis"""
        client = await self.connect()
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None


redis_service = RedisService()
