import asyncio
import logging
import sys

import aranet4

async def main(argv):
    logger = logging.getLogger()
    #logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    logging.info("Connecting to Aranet4...")
    aranet = aranet4.Aranet4("2AEA3C6F-F1BC-3359-E099-293CA3C84D94")
    async with aranet as device:
        logging.info("Connected!")

        readings = await device.fetch_current_readings()
        logging.info("Current readings: %s", readings)

        historical = await device.fetch_historical_readings()
        for time, data in historical.items():
            logging.info("%s: %s", time, data)
        logging.info("Total of %d historical readings", len(historical))


if __name__ == "__main__":
    asyncio.run(main(sys.argv))
