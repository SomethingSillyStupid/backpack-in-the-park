import uasyncio, usocket
from . import logging
from captive_portal import build_dns_response

async def _handler(socket, ip_address):
  while True:
    try:
      yield uasyncio.core._io_queue.queue_read(socket)
      request, client = socket.recvfrom(256)
      response = build_dns_response(request, ip_address)
      if response is not None:
        socket.sendto(response, client)
    except Exception as e:
      logging.error(e)

def run_catchall(ip_address, port=53):
  logging.info("> starting catch all dns server on port {}".format(port))

  _socket = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
  _socket.setblocking(False)
  _socket.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
  _socket.bind(usocket.getaddrinfo(ip_address, port, 0, usocket.SOCK_DGRAM)[0][-1])

  loop = uasyncio.get_event_loop()
  loop.create_task(_handler(_socket, ip_address))