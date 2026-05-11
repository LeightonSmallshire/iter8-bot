import logfire


logfire.configure(token='pylf_v1_eu_mNQFSx13Z0SFKvkzMPHpjYGzLcTD2Gf8JNyhzV6ZDqF1')

try:
    import main
except BaseException as e:
    logfire.error('Error: ', e)
