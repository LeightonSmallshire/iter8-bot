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

IS_LIVE = os.environ.get('MODE', '') == 'Live'
logfire.configure(environment='Live' if IS_LIVE else 'Testing')

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
