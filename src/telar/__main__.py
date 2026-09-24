"""`python -m telar`: lo mismo que el programa `telar`, sin depender del PATH."""

import sys

from telar.cli import main

sys.exit(main(sys.argv[1:]))
