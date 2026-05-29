import logging
import os
import traceback

import dotenv
import logfire

if __name__ != "__main__":
    raise RuntimeError('Must be run directly')


os.chdir(os.path.dirname(__file__))

dotenv.load_dotenv('data/.env')
dotenv.load_dotenv('../AutoDeploy/.env')
dotenv.load_dotenv()

# Route LangChain/LangGraph tracing through Logfire instead of smith.langchain.com
os.environ.setdefault('LANGSMITH_OTEL_ENABLED', 'true')
os.environ.setdefault('LANGSMITH_OTEL_ONLY', 'true')

IS_LIVE = os.environ.get('MODE', '') == 'Live'

# langsmith OTel exporter iterates over metadata dicts and blindly sets
# them as span attributes, which triggers OTel warnings when a value is a
# nested dict (e.g. usage_metadata).  Noisy, harmless — silence it.
logging.getLogger('opentelemetry.attributes').setLevel(logging.ERROR)

logfire.configure(
    environment='Live' if IS_LIVE else 'Testing',
    console=logfire.ConsoleOptions(min_log_level="debug")
)

with logfire.span('Running'):
    try:
        import main
        main.main()

    except BaseException as e:
        traceback.print_exception(e)
        lines = traceback.format_exception(e)
        message = ''.join(lines)
        logfire.exception('Uncaught exception:', traceback=e, lines=message)
        raise e
