import logfire
import traceback


logfire.configure(token='pylf_v1_eu_mNQFSx13Z0SFKvkzMPHpjYGzLcTD2Gf8JNyhzV6ZDqF1')
logfire.info('Starting')

try:
    import main
except BaseException as e:
    logfire.exception('Uncaught exception')
