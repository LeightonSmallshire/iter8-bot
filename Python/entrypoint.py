import json
import os
import http.client
import logfire
import traceback


logfire.configure(token='pylf_v1_eu_mNQFSx13Z0SFKvkzMPHpjYGzLcTD2Gf8JNyhzV6ZDqF1')

with logfire.span('Running'):
    try:
        assert __name__ == "__main__", 'Must be run directly'

        DISCORD_WEBOOK_ID = os.environ['DISCORD_WEBHOOK_ID']
        DISCORD_WEBOOK_TOKEN = os.environ['DISCORD_WEBHOOK_TOKEN']

        def do_hook(message: str):
            for i in range(0, len(message), 1900):
                suppress_notifications = 1 << 12
                payload = json.dumps({'content': '```' + message[i:i+1900] + '```', 'flags': suppress_notifications})
                conn = http.client.HTTPSConnection('discord.com')
                conn.request(method='POST',
                             url=f'/api/webhooks/{DISCORD_WEBOOK_ID}/{DISCORD_WEBOOK_TOKEN}',
                             body=payload, headers={'Content-Type': 'application/json'})
                response = conn.getresponse()
                print(response)
                conn.close()

        do_hook('Starting 3')

        import main
    except BaseException as e:
        traceback.print_exception(e)
        lines = traceback.format_exception(e)
        message = ''.join(lines)
        do_hook(message)
        logfire.exception('Uncaught exception:', traceback=e, lines=message)
        raise e
