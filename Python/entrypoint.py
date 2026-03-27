import http.client
import traceback
import os
import json

assert __name__ == "__main__", 'Must be run directly'

DISCORD_WEBOOK_ID = os.environ['DISCORD_WEBOOK_ID']
DISCORD_WEBOOK_TOKEN = os.environ['DISCORD_WEBOOK_TOKEN']


def do_hook(message: str) -> None:
    suppress_notifications = 1 << 12
    payload = json.dumps({'content': '```' + message + '```', 'flags': suppress_notifications})
    conn = http.client.HTTPSConnection('discord.com')
    conn.request(method='POST',
                 url=f'/api/webhooks/{DISCORD_WEBOOK_ID}/{DISCORD_WEBOOK_TOKEN}',
                 body=payload, headers={'Content-Type': 'application/json'})
    response = conn.getresponse()
    print(response)
    conn.close()


try:
    pass
except BaseException as e:
    traceback.print_exception(e)
    lines = traceback.format_exception(e)
    message = ''.join(lines)
    do_hook(message)
    raise e
