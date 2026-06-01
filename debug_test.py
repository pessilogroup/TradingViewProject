import sys
import asyncio
sys.path.insert(0, 'nerves/workers/trading')
from workers.vps_consumer import VpsSignalConsumer

async def main():
    consumer = VpsSignalConsumer()
    print("hasattr _session:", hasattr(consumer, "_session"))
    try:
        sess = await consumer.get_session()
        print("get_session returned:", sess)
    except Exception as e:
        print("get_session raised:", type(e), str(e))

asyncio.run(main())
