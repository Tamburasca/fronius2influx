import asyncio
from src import fronius2influx, fronius2influx_async

fronius2influx.main()
# asyncio.run(fronius2influx_async.main())
