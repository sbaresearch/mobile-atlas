import logging

from moatt_server.rest import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    app.run()
