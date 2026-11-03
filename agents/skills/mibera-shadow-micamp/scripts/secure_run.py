"""Interactive operator entrypoint: never put a password in CLI arguments."""
import getpass,os
if not os.environ.get('MIBERA_SESSION_PASSWORD'):
    os.environ['MIBERA_SESSION_PASSWORD']=getpass.getpass('Local session encryption password (16+ characters): ')
from mibera import main
main()
